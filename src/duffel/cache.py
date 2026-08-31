import json
import logging
import threading
import time
from typing import Any, Optional

from .config import DuffelConfig

logger = logging.getLogger("duffel.cache")

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class DuffelCache:
    """
    Caching manager for Duffel API responses.
    Uses Redis when available, falling back gracefully to In-Memory Cache.
    """

    def __init__(self, config: DuffelConfig):
        self.config = config
        self.enabled = config.enable_cache
        self.debug = config.debug
        self.ttl = config.cache_ttl_seconds
        self.redis_client: Optional[Any] = None
        self.in_memory_store: dict[str, tuple[float, str]] = {}
        self.hits: int = 0
        self.tier1_hits: int = 0
        self.tier2_hits: int = 0
        self.misses: int = 0
        self.writes_count: int = 0
        self.read_latencies: list[float] = []
        self.write_latencies: list[float] = []
        self._lock = threading.Lock()

        if self.enabled and REDIS_AVAILABLE:
            hosts_to_try = [config.redis_host]
            if config.redis_host in ("127.0.0.1", "localhost"):
                hosts_to_try = ["127.0.0.1", "localhost"]

            last_err = None
            for h in hosts_to_try:
                try:
                    redis_kwargs = {
                        "host": h,
                        "port": config.redis_port,
                        "db": config.redis_db,
                        "socket_connect_timeout": 0.5,
                        "socket_timeout": 0.5,
                        "health_check_interval": 0,
                        "decode_responses": True,
                    }
                    if hasattr(redis, "retry") and hasattr(redis.retry, "Retry") and hasattr(redis, "backoff") and hasattr(redis.backoff, "NoBackoff"):
                        redis_kwargs["retry"] = redis.retry.Retry(redis.backoff.NoBackoff(), 0)

                    if config.redis_password:
                        redis_kwargs["password"] = config.redis_password

                    r = redis.Redis(**redis_kwargs)
                    r.ping()
                    self.redis_client = r
                    if self.debug:
                        print(f"\n[+] Connected to Redis Cache at {h}:{config.redis_port}\n")
                    logger.info("Connected to Redis cache at %s:%s", h, config.redis_port)
                    break
                except Exception as err:
                    last_err = err
                    if self.debug:
                        print(f"\n[!] Redis Connection attempt to {h}:{config.redis_port} failed: {type(err).__name__}: {err}\n")

            if self.redis_client is None:
                err_msg = f"[REDIS NOTICE] Could not connect to Redis server at {config.redis_host}:{config.redis_port} ({type(last_err).__name__}: {last_err}). Falling back to in-memory L1 cache."
                logger.warning(err_msg)
                if self.debug:
                    print(f"\n{'=' * 80}\n{err_msg}\n{'=' * 80}\n")

    def clear_metrics(self) -> None:
        """Reset cache hits, misses, writes, and latency metrics."""
        with self._lock:
            self.hits = 0
            self.tier1_hits = 0
            self.tier2_hits = 0
            self.misses = 0
            self.writes_count = 0
            self.read_latencies.clear()
            self.write_latencies.clear()
            self._current_cache_hits = 0
            self._current_records_retrieved = 0
            self._current_cache_writes = 0
            self._current_records_written = 0

    def reset_request_stats(self) -> None:
        """Reset per-request cache hit, write, and record count metrics."""
        with self._lock:
            self._current_cache_hits = 0
            self._current_records_retrieved = 0
            self._current_cache_writes = 0
            self._current_records_written = 0

    def get_request_stats(self) -> dict[str, Any]:
        """Return cache hit status, retrieved records, and written records count for current request cycle."""
        with self._lock:
            hits = getattr(self, "_current_cache_hits", 0)
            retrieved = getattr(self, "_current_records_retrieved", 0)
            writes = getattr(self, "_current_cache_writes", 0)
            written = getattr(self, "_current_records_written", 0)
            return {
                "cache_hit": hits > 0,
                "hits_count": hits,
                "records_retrieved": retrieved,
                "writes_count": writes,
                "records_written": written,
            }

    def _record_retrieved_items(self, val: Any) -> None:
        count = 0
        if isinstance(val, list):
            count = len(val)
        elif isinstance(val, dict):
            if "results" in val and isinstance(val["results"], list):
                count = len(val["results"])
            elif "offers" in val and isinstance(val["offers"], list):
                count = len(val["offers"])
            else:
                count = 1
        elif val is not None:
            count = 1

        with self._lock:
            self._current_cache_hits = getattr(self, "_current_cache_hits", 0) + 1
            self._current_records_retrieved = getattr(self, "_current_records_retrieved", 0) + count

    def _record_written_items(self, val: Any) -> None:
        count = 0
        if isinstance(val, list):
            count = len(val)
        elif isinstance(val, dict):
            if "results" in val and isinstance(val["results"], list):
                count = len(val["results"])
            elif "offers" in val and isinstance(val["offers"], list):
                count = len(val["offers"])
            else:
                count = 1
        elif val is not None:
            count = 1

        with self._lock:
            self._current_cache_writes = getattr(self, "_current_cache_writes", 0) + 1
            self._current_records_written = getattr(self, "_current_records_written", 0) + count

    def get(self, key: str) -> Optional[Any]:
        """Retrieve cached object by key, or return None if missed/expired."""
        if not self.enabled:
            return None

        t0 = time.perf_counter()
        res = None

        # 1. Try Redis
        if self.redis_client is not None:
            try:
                raw_val = self.redis_client.get(key)
                if raw_val is not None:
                    res = json.loads(raw_val)
                    with self._lock:
                        self.hits += 1
                        if "search_optimized:" in key:
                            self.tier1_hits += 1
                        else:
                            self.tier2_hits += 1
                    self._record_retrieved_items(res)
                    if self.debug:
                        logger.debug("[REDIS CACHE HIT] Key: %s | Value: %s", key, raw_val[:300])
                    logger.debug("Redis Cache HIT for key: %s", key)
            except Exception as err:
                self.redis_client = None
                if self.debug:
                    logger.debug("[!] REDIS READ EXCEPTION: %s: %s", type(err).__name__, err)
                logger.warning("Redis read error (%s). Checking in-memory cache.", err)

        # 2. Fallback to In-Memory store
        if res is None and key in self.in_memory_store:
            expiry_time, raw_val = self.in_memory_store[key]
            if time.time() < expiry_time:
                res = json.loads(raw_val)
                with self._lock:
                    self.hits += 1
                    if "search_optimized:" in key:
                        self.tier1_hits += 1
                    else:
                        self.tier2_hits += 1
                self._record_retrieved_items(res)
                if self.debug:
                    logger.debug("[IN-MEMORY CACHE HIT] Key: %s | Value: %s", key, raw_val[:300])
                logger.debug("In-Memory Cache HIT for key: %s", key)
            else:
                del self.in_memory_store[key]

        if res is None:
            with self._lock:
                self.misses += 1

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        with self._lock:
            self.read_latencies.append(elapsed_ms)
        try:
            from .timing import TimingTracker
            TimingTracker.add_redis_read_time(elapsed_ms)
        except Exception:
            pass
        return res

    def exists(self, key: str) -> bool:
        """Check if a key exists in Redis or In-Memory store without affecting hit/miss metrics."""
        if not self.enabled:
            return False
        if self.redis_client is not None:
            try:
                return bool(self.redis_client.exists(key))
            except Exception as err:
                self.redis_client = None
                if self.debug:
                    print(f"\n[!] REDIS EXISTS CHECK EXCEPTION: {type(err).__name__}: {err}\n")
        if key in self.in_memory_store:
            expiry_time, _ = self.in_memory_store[key]
            if time.time() < expiry_time:
                return True
            else:
                del self.in_memory_store[key]
        return False

    def get_key_size_bytes(self, key: str) -> int:
        """Get payload byte size for a cached key."""
        if not self.enabled:
            return 0
        if self.redis_client is not None:
            try:
                slen = self.redis_client.strlen(key)
                if slen:
                    return slen
                mem = self.redis_client.memory_usage(key)
                if mem:
                    return mem
            except Exception:
                pass
        if key in self.in_memory_store:
            _, raw = self.in_memory_store[key]
            return len(raw.encode("utf-8")) if isinstance(raw, str) else len(raw)
        return 0

    def is_empty_result(self, value: Any) -> bool:
        """Check if a search result payload contains no data / empty items."""
        if value is None:
            return True
        if isinstance(value, (list, tuple, set)) and len(value) == 0:
            return True
        if isinstance(value, dict):
            if len(value) == 0:
                return True
            res_list = value.get("results") or value.get("offers") or value.get("top_offers") or value.get("top_bundles")
            if res_list is not None and isinstance(res_list, list) and len(res_list) == 0:
                return True
            if value.get("total_results") == 0 or value.get("total_bundles_found") == 0 or value.get("total_items") == 0:
                return True
            if "data" in value and isinstance(value["data"], dict):
                inner = value["data"]
                inner_items = inner.get("offers") or inner.get("results") or inner.get("top_bundles")
                if inner_items is not None and isinstance(inner_items, list) and len(inner_items) == 0:
                    return True
                if inner.get("total_items") == 0 or inner.get("total_results") == 0:
                    return True
        return False

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store or update value in cache with TTL. Empty/no-data results write with 120s (2 min) TTL."""
        t0 = time.perf_counter()
        if ttl_seconds is not None:
            ttl = ttl_seconds
        elif self.is_empty_result(value):
            ttl = 120  # Negative cache TTL for empty / no-data search results (2 minutes)
        else:
            ttl = self.ttl

        try:
            json_val = json.dumps(value)
        except Exception:
            def _json_default(obj):
                if hasattr(obj, "to_dict"):
                    return obj.to_dict()
                if hasattr(obj, "__dict__"):
                    return obj.__dict__
                return str(obj)
            json_val = json.dumps(value, default=_json_default)


        # 1. Store in Redis if available
        if self.redis_client is not None:
            try:
                self.redis_client.set(key, json_val, ex=ttl)
                if self.debug:
                    print(f"\n[REDIS CACHE WRITE]")
                    print(f"  * Key   : {key}")
                    print(f"  * TTL   : {ttl} seconds")
                    print(f"  * Value : {json_val[:300]}{'...' if len(json_val) > 300 else ''}\n")
                logger.debug("Stored key %s in Redis cache with TTL %ds", key, ttl)
            except Exception as err:
                self.redis_client = None
                if self.debug:
                    print(f"\n[!] REDIS WRITE EXCEPTION: {type(err).__name__}: {err}\n")
                logger.warning("Redis write error (%s). Storing in memory.", err)

        # 2. Store in In-Memory fallback
        expiry_time = time.time() + ttl
        self.in_memory_store[key] = (expiry_time, json_val)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        with self._lock:
            self.writes_count += 1
            self.write_latencies.append(elapsed_ms)
        try:
            from .timing import TimingTracker
            TimingTracker.add_redis_write_time(elapsed_ms)
        except Exception:
            pass
        self._record_written_items(value)

    def delete(self, key: str) -> None:
        """Evict/delete a specific cache key from Redis and In-Memory store."""
        if self.redis_client is not None:
            try:
                self.redis_client.delete(key)
            except Exception as err:
                if self.debug:
                    print(f"\n[!] REDIS DELETE EXCEPTION: {type(err).__name__}: {err}\n")
        self.in_memory_store.pop(key, None)

    def evict(self, key: str) -> None:
        """Alias for delete."""
        self.delete(key)

    def get_count(self) -> int:
        """Return total count of cached records in Redis and In-Memory store."""
        count = 0
        if self.redis_client is not None:
            try:
                keys = self.redis_client.keys("*")
                count += len(keys)
            except Exception as err:
                logger.error("Failed to count Redis keys: %s", err)
        count += len(self.in_memory_store)
        return count

    def clear(self) -> None:
        """Clear all cached entries in Redis and In-Memory store."""
        before_count = self.get_count()
        print(f"\n[CACHE CLEAR] Record count BEFORE clearing: {before_count}")

        if self.redis_client is not None:
            try:
                keys = self.redis_client.keys("*")
                if keys:
                    self.redis_client.delete(*keys)
                self.redis_client.flushdb()
                try:
                    self.redis_client.flushall()
                except Exception:
                    pass
                print("[+] Flushed Redis database successfully.")
            except Exception as err:
                print(f"[!] Error flushing Redis cache: {err}")

        mem_count = len(self.in_memory_store)
        self.in_memory_store.clear()
        with self._lock:
            self.hits = 0
            self.tier1_hits = 0
            self.tier2_hits = 0
            self.misses = 0
            self.writes_count = 0
            self.read_latencies.clear()
            self.write_latencies.clear()

        after_count = self.get_count()
        print(f"[CACHE CLEAR] Record count AFTER clearing: {after_count}\n")

    def get_metrics_summary(self) -> dict[str, Any]:
        """Return detailed cache performance & latency metrics summary."""
        with self._lock:
            hits = self.hits
            t1_hits = self.tier1_hits
            t2_hits = self.tier2_hits
            misses = self.misses
            writes = self.writes_count
            r_lats = list(self.read_latencies)
            w_lats = list(self.write_latencies)

        total_reads = hits + misses
        hit_pct = (hits / total_reads * 100.0) if total_reads > 0 else 0.0
        miss_pct = (misses / total_reads * 100.0) if total_reads > 0 else 0.0

        r_min = min(r_lats) if r_lats else 0.0
        r_max = max(r_lats) if r_lats else 0.0
        r_avg = (sum(r_lats) / len(r_lats)) if r_lats else 0.0

        w_min = min(w_lats) if w_lats else 0.0
        w_max = max(w_lats) if w_lats else 0.0
        w_avg = (sum(w_lats) / len(w_lats)) if w_lats else 0.0

        backend = "redis" if self.redis_client is not None else ("in_memory" if self.enabled else "disabled")
        return {
            "enabled": self.enabled,
            "backend": backend,
            "redis_host": self.config.redis_host if self.redis_client else None,
            "total_reads": total_reads,
            "hits": hits,
            "tier1_hits": t1_hits,
            "tier2_hits": t2_hits,
            "aggregated_cache_hits": t1_hits,
            "individual_cache_hits": t2_hits,
            "misses": misses,
            "hit_percentage": round(hit_pct, 1),
            "miss_percentage": round(miss_pct, 1),
            "writes": writes,
            "miss_percentage": round(miss_pct, 1),
            "writes": writes,
            "read_min_ms": round(r_min, 2),
            "read_max_ms": round(r_max, 2),
            "read_avg_ms": round(r_avg, 2),
            "write_min_ms": round(w_min, 2),
            "write_max_ms": round(w_max, 2),
            "write_avg_ms": round(w_avg, 2),
            "ttl_seconds": self.ttl,
        }

    def calculate_earliest_ttl(self, records: Any, default_ttl: Optional[int] = None) -> tuple[int, str]:
        """
        Calculates remaining TTL in seconds and ISO expiration timestamp based on the earliest expiry date
        among all records (offers, stay quotes, car offers, package items).
        Returns tuple: (ttl_seconds, expires_at_iso_string)
        """
        from datetime import datetime, timedelta, timezone

        def_ttl = default_ttl if default_ttl is not None else self.ttl
        now_utc = datetime.now(timezone.utc)
        earliest_expiry: Optional[datetime] = None

        raw_records = records or []
        if isinstance(raw_records, dict):
            raw_records = [raw_records]

        if not raw_records or len(raw_records) == 0:
            expires_at_dt = now_utc + timedelta(seconds=120)
            return 120, expires_at_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        for rec in raw_records:
            if not rec:
                continue
            exp_str = None
            if isinstance(rec, dict):
                exp_str = (
                    rec.get("expires_at")
                    or rec.get("price_guarantee_expires_at")
                    or (rec.get("payment_requirements") or {}).get("price_guarantee_expires_at")
                )
                if not exp_str and "flight_offer" in rec:
                    exp_str = (rec.get("flight_offer") or {}).get("expires_at")
            else:
                exp_str = getattr(rec, "expires_at", None)

            if exp_str:
                try:
                    clean_str = str(exp_str).replace("Z", "+00:00")
                    dt = datetime.fromisoformat(clean_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if earliest_expiry is None or dt < earliest_expiry:
                        earliest_expiry = dt
                except Exception:
                    pass

        if earliest_expiry is not None:
            rem_sec = int((earliest_expiry - now_utc).total_seconds())
            if rem_sec > 0:
                final_ttl = min(rem_sec, def_ttl)
                expires_at_dt = now_utc + timedelta(seconds=final_ttl)
                return final_ttl, expires_at_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        expires_at_dt = now_utc + timedelta(seconds=def_ttl)
        return def_ttl, expires_at_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


    
    def set_records_batch(self, category_or_records: Any = None, records: Any = None, id_key: Optional[str] = None, ttl_seconds: Optional[int] = None, **kwargs) -> None:
        """Store multiple key-value pairs in cache in a batch operation."""
        if not self.enabled:
            return
        
        target_records = records if records is not None else category_or_records
        if not target_records:
            return
        
        prefix = f"{category_or_records}:" if (records is not None and isinstance(category_or_records, str)) else ""

        items = target_records.items() if isinstance(target_records, dict) else target_records
        for item in items:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                key, val = item
                self.set(f"{prefix}{key}", val, ttl_seconds=ttl_seconds)
            elif isinstance(item, str) and isinstance(target_records, dict):
                self.set(f"{prefix}{item}", target_records[item], ttl_seconds=ttl_seconds)
            elif isinstance(item, dict) and id_key and id_key in item:
                self.set(f"{prefix}{item[id_key]}", item, ttl_seconds=ttl_seconds)

    def record_search_event(self, search_event: dict[str, Any]) -> None:
        """Record a search execution event with API vs Cache hit metrics."""
        history_key = "duffel:metrics:search_history"
        json_event = json.dumps(search_event)

        if self.redis_client is not None:
            try:
                self.redis_client.lpush(history_key, json_event)
                # Keep last 100 search events
                self.redis_client.ltrim(history_key, 0, 99)
                return
            except Exception as err:
                if self.debug:
                    print(f"\n[!] ERROR recording search event in Redis: {err}\n")

        with self._lock:
            if not hasattr(self, "_in_memory_history"):
                self._in_memory_history: list[dict[str, Any]] = []
            self._in_memory_history.insert(0, search_event)
            self._in_memory_history = self._in_memory_history[:100]

    def get_search_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent per-search metrics history (cache hits, API calls, routes)."""
        history_key = "duffel:metrics:search_history"
        if self.redis_client is not None:
            try:
                raw_items = self.redis_client.lrange(history_key, 0, limit - 1)
                return [json.loads(item) for item in raw_items]
            except Exception as err:
                if self.debug:
                    print(f"\n[!] ERROR retrieving search history from Redis: {err}\n")

        with self._lock:
            if hasattr(self, "_in_memory_history"):
                return self._in_memory_history[:limit]
            return []

    @property
    def status_info(self) -> dict[str, Any]:
        """Return summary of cache status and active backend."""
        backend = "redis" if self.redis_client is not None else "in_memory"
        return {
            "enabled": self.enabled,
            "backend": backend,
            "ttl_seconds": self.ttl,
            "redis_host": self.config.redis_host if self.redis_client else None,
        }
