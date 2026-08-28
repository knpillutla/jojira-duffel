"""
REST Client executing HTTP requests against Duffel API endpoints.
"""

import json
import logging
import random
import socket
import threading
import time
from typing import Any, Optional, Union
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .config import DuffelConfig
from .exceptions import (
    DuffelAPIError,
    DuffelAuthenticationError,
    DuffelException,
    DuffelNotFoundError,
    DuffelRateLimitError,
    DuffelValidationError,
)

logger = logging.getLogger("duffel")


class HTTPClient:
    """REST Client executing HTTP requests against Duffel API endpoints."""

    def __init__(self, config: DuffelConfig):
        self.config = config
        self._lock = threading.Lock()
        self.metrics: list[dict[str, Any]] = []
        self._current_api_calls: int = 0
        self._current_delayed_calls: int = 0

    def reset_request_stats(self):
        """Reset per-request API call and delayed call counters."""
        with self._lock:
            self._current_api_calls = 0
            self._current_delayed_calls = 0

    def get_request_stats(self) -> dict[str, int]:
        """Return counts of Duffel API calls and rate-limit delayed calls made during current request."""
        with self._lock:
            return {
                "api_calls": self._current_api_calls,
                "delayed_calls": self._current_delayed_calls,
            }

    def clear_metrics(self):
        """Reset recorded HTTP call metrics."""
        with self._lock:
            self.metrics.clear()
            self._current_api_calls = 0
            self._current_delayed_calls = 0

    def get_metrics_summary(self) -> dict[str, Any]:
        """Compute total call count, min, max, and avg response times in milliseconds."""
        with self._lock:
            if not self.metrics:
                return {
                    "total_calls": 0,
                    "min_ms": 0.0,
                    "max_ms": 0.0,
                    "avg_ms": 0.0,
                }
            durations = [m["duration_ms"] for m in self.metrics]
            return {
                "total_calls": len(durations),
                "min_ms": min(durations),
                "max_ms": max(durations),
                "avg_ms": sum(durations) / len(durations),
            }

    def request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Execute an HTTP request to the Duffel API with automatic retries for transient errors.

        :param method: HTTP method (GET, POST, PATCH, DELETE)
        :param path: API path starting with / (e.g. /air/offers)
        :param params: Optional query string parameters
        :param data: Optional JSON serializable body dictionary
        :param headers: Optional custom HTTP headers
        :param idempotency_key: Optional idempotency key for safe retries
        :param timeout: Optional read timeout in seconds (defaults to 130.0s)
        :return: Decoded JSON response dictionary
        """
        url = self._build_url(path, params)
        req_headers = dict(self.config.headers)
        if headers:
            req_headers.update(headers)

        if idempotency_key:
            req_headers["Duffel-Idempotency-Key"] = str(idempotency_key)
        elif method.upper() in ["POST", "PATCH"] and "Duffel-Idempotency-Key" not in req_headers:
            req_headers["Duffel-Idempotency-Key"] = str(uuid.uuid4())

        body_bytes: Optional[bytes] = None

        if data is not None:
            body_bytes = json.dumps(data).encode("utf-8")

        total_attempts = 3  # Max 3 attempts (1 initial + 2 retries)
        backoff_factor = getattr(self.config, "retry_backoff_factor", 0.5)
        backoff_max = getattr(self.config, "retry_backoff_max", 10.0)
        retry_status_codes = set(getattr(self.config, "retry_status_codes", [500, 502, 503, 504, 429]) or [500, 502, 503, 504, 429])

        req_timeout = timeout if timeout is not None else getattr(self.config, "timeout", 5.0)

        for attempt in range(1, total_attempts + 1):
            # Throttle request rate if a 429 rate limit was recently encountered (max 1 call/sec)
            with self._lock:
                last_429 = getattr(self, "_last_429_time", 0.0)
            if last_429 > 0:
                since_429 = time.time() - last_429
                if since_429 < 1.0:
                    time.sleep(1.0 - since_429)

            if self.config.debug:
                logger.debug("[DUFFEL API REQUEST] %s %s (Attempt %d/%d)", method.upper(), url, attempt, total_attempts)
                if data and attempt == 1:
                    logger.debug("Duffel Request Payload:\n%s", json.dumps(data, indent=2))

            req = urllib.request.Request(
                url=url,
                data=body_bytes,
                headers=req_headers,
                method=method.upper(),
            )

            start_time = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=req_timeout) as response:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    with self._lock:
                        self.metrics.append({"path": path, "duration_ms": elapsed_ms, "status": response.status})
                        self._current_api_calls = getattr(self, "_current_api_calls", 0) + 1

                    res_body = response.read().decode("utf-8")
                    if not res_body.strip():
                        logger.debug("[DUFFEL API RESPONSE] Status %d (%.1fms) -> Empty Body", response.status, elapsed_ms)
                        return {}
                    parsed = json.loads(res_body)
                    if self.config.debug:
                        logger.debug("[DUFFEL API RESPONSE] Status %d (%.1fms)", response.status, elapsed_ms)
                    return parsed
            except urllib.error.HTTPError as err:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                with self._lock:
                    self.metrics.append({"path": path, "duration_ms": elapsed_ms, "status": err.code})
                    self._current_api_calls = getattr(self, "_current_api_calls", 0) + 1
                    if err.code == 429:
                        self._last_429_time = time.time()
                        self._current_delayed_calls = getattr(self, "_current_delayed_calls", 0) + 1

                err_body = err.read().decode("utf-8")

                if err.code in retry_status_codes and attempt < total_attempts:
                    retry_after = None
                    if err.headers:
                        retry_after = (
                            err.headers.get("ratelimit-reset")
                            or err.headers.get("Ratelimit-Reset")
                            or err.headers.get("Retry-After")
                            or err.headers.get("retry-after")
                        )
                    delay = None
                    if retry_after:
                        try:
                            val = float(retry_after)
                            if val > 1000000000:
                                delay = max(1.0, val - time.time())
                            else:
                                delay = max(1.0, val)
                        except ValueError:
                            pass
                    if delay is None:
                        base_delay = min(backoff_max, backoff_factor * (2 ** (attempt - 1)))
                        delay = random.uniform(0.5 * base_delay, base_delay)

                    # Enforce a 1.0 second minimum backoff floor for 429 Rate Limit Exceeded
                    if err.code == 429:
                        delay = max(1.0, delay if delay is not None else 1.0)
                        msg = (
                            f"[DUFFEL 429 RATE LIMIT BACKOFF] HTTP 429 Rate Limit Exceeded (ratelimit-reset: {retry_after or 'N/A'}). "
                            f"Throttling execution to 1 call per second (pausing {delay:.2f}s before retry {attempt}/{total_attempts - 1})... "
                            f"(Idempotency Key: {req_headers.get('Duffel-Idempotency-Key', 'N/A')})"
                        )
                    else:
                        msg = (
                            f"[DUFFEL API RETRY] {method.upper()} {path} returned status {err.code}. "
                            f"Retrying attempt {attempt + 1}/{total_attempts} in {delay:.2f}s... "
                            f"(Idempotency Key: {req_headers.get('Duffel-Idempotency-Key', 'N/A')})"
                        )
                    logger.warning(msg)
                    print(msg)
                    time.sleep(delay)
                    continue

                print(f"[DUFFEL API ERROR] Status {err.code} ({elapsed_ms:.1f}ms):\n{err_body}")
                print("=" * 80 + "\n")
                return self._handle_http_error(err.code, err_body)

            except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError) as err:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                with self._lock:
                    self.metrics.append({"path": path, "duration_ms": elapsed_ms, "status": 0})

                if attempt < total_attempts:
                    base_delay = min(backoff_max, backoff_factor * (2 ** (attempt - 1)))
                    delay = random.uniform(0.5 * base_delay, base_delay)
                    msg = (
                        f"[DUFFEL NETWORK RETRY] {method.upper()} {path} failed: {err}. "
                        f"Retrying attempt {attempt + 1}/{total_attempts} in {delay:.2f}s..."
                    )
                    logger.warning(msg)
                    print(msg)
                    time.sleep(delay)
                    continue

                raise DuffelException(f"Network error communicating with Duffel API after {total_attempts} attempts: {err}") from err
            except Exception as err:
                raise DuffelException(f"Unexpected error: {str(err)}") from err

        raise DuffelException("Unexpected error: Exhausted retries without returning or throwing.")

    def get(self, path: str, params: Optional[dict[str, Any]] = None, headers: Optional[dict[str, str]] = None, timeout: Optional[float] = None) -> dict[str, Any]:
        """Shortcut for GET request."""
        return self.request("GET", path, params=params, headers=headers, timeout=timeout)

    def post(
        self,
        path: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Shortcut for POST request."""
        return self.request("POST", path, params=params, data=data, headers=headers, idempotency_key=idempotency_key, timeout=timeout)

    def patch(
        self,
        path: str,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Shortcut for PATCH request."""
        return self.request("PATCH", path, data=data, headers=headers, idempotency_key=idempotency_key, timeout=timeout)

    def delete(self, path: str, headers: Optional[dict[str, str]] = None, timeout: Optional[float] = None) -> dict[str, Any]:
        """Shortcut for DELETE request."""
        return self.request("DELETE", path, headers=headers, timeout=timeout)

    def _build_url(self, path: str, params: Optional[dict[str, Any]] = None) -> str:
        base = self.config.base_url.rstrip("/")
        clean_path = "/" + path.lstrip("/")
        full_url = f"{base}{clean_path}"

        if params:
            filtered_params = {k: v for k, v in params.items() if v is not None}
            if filtered_params:
                query_string = urllib.parse.urlencode(filtered_params, doseq=True)
                full_url = f"{full_url}?{query_string}"

        return full_url

    def _handle_http_error(self, status_code: int, error_body: str) -> dict[str, Any]:
        parsed_body: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []
        message = f"HTTP {status_code} Error"

        try:
            parsed_body = json.loads(error_body)
            if "errors" in parsed_body and isinstance(parsed_body["errors"], list):
                errors = parsed_body["errors"]
                if errors and "message" in errors[0]:
                    message = errors[0]["message"]
            elif "message" in parsed_body:
                message = parsed_body["message"]
        except Exception:
            message = error_body or message

        if status_code == 401:
            raise DuffelAuthenticationError(message, status_code, errors, parsed_body)
        elif status_code == 404:
            raise DuffelNotFoundError(message, status_code, errors, parsed_body)
        elif status_code == 422:
            raise DuffelValidationError(message, status_code, errors, parsed_body)
        elif status_code == 429:
            raise DuffelRateLimitError(message, status_code, errors, parsed_body)
        else:
            raise DuffelAPIError(message, status_code, errors, parsed_body)
