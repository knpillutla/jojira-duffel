import json
import logging
import threading
import time
from typing import Any, Optional, Union
import urllib.error
import urllib.parse
import urllib.request

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

    def clear_metrics(self):
        """Reset recorded HTTP call metrics."""
        with self._lock:
            self.metrics.clear()

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
    ) -> dict[str, Any]:
        """
        Execute an HTTP request to the Duffel API.

        :param method: HTTP method (GET, POST, PATCH, DELETE)
        :param path: API path starting with / (e.g. /air/offers)
        :param params: Optional query string parameters
        :param data: Optional JSON serializable body dictionary
        :return: Decoded JSON response dictionary
        """
        url = self._build_url(path, params)
        headers = self.config.headers
        body_bytes: Optional[bytes] = None

        if data is not None:
            body_bytes = json.dumps(data).encode("utf-8")

        if self.config.debug:
            logger.debug("Executing Duffel Request: %s %s", method, url)
            if data:
                logger.debug("Request Payload: %s", data)

        req = urllib.request.Request(
            url=url,
            data=body_bytes,
            headers=headers,
            method=method.upper(),
        )

        start_time = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                with self._lock:
                    self.metrics.append({"path": path, "duration_ms": elapsed_ms, "status": response.status})

                res_body = response.read().decode("utf-8")
                if not res_body.strip():
                    return {}
                parsed = json.loads(res_body)
                if self.config.debug:
                    logger.debug("Response Payload: %s", parsed)
                return parsed
        except urllib.error.HTTPError as err:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            with self._lock:
                self.metrics.append({"path": path, "duration_ms": elapsed_ms, "status": err.code})

            err_body = err.read().decode("utf-8")
            return self._handle_http_error(err.code, err_body)
        except urllib.error.URLError as err:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            with self._lock:
                self.metrics.append({"path": path, "duration_ms": elapsed_ms, "status": 0})
            raise DuffelException(f"Network error communicating with Duffel API: {err.reason}") from err
        except Exception as err:
            raise DuffelException(f"Unexpected error: {str(err)}") from err

    def get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Shortcut for GET request."""
        return self.request("GET", path, params=params)

    def post(self, path: str, data: Optional[dict[str, Any]] = None, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Shortcut for POST request."""
        return self.request("POST", path, params=params, data=data)

    def patch(self, path: str, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Shortcut for PATCH request."""
        return self.request("PATCH", path, data=data)

    def delete(self, path: str) -> dict[str, Any]:
        """Shortcut for DELETE request."""
        return self.request("DELETE", path)

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
