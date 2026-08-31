"""
Thread-safe performance timing tracker for Duffel API, LLM, Redis, and Algorithm execution.
"""

from dataclasses import dataclass
import threading
import time
from typing import Any, Optional


@dataclass
class PerformanceMetrics:
    total_execution_ms: float = 0.0
    llm_execution_ms: float = 0.0
    duffel_api_ms: float = 0.0
    redis_read_ms: float = 0.0
    redis_write_ms: float = 0.0
    algorithm_synthesis_ms: float = 0.0


_local = threading.local()


class TimingTracker:
    """Thread-local timing tracker for fine-grained performance breakdown."""

    @staticmethod
    def reset() -> None:
        _local.metrics = PerformanceMetrics()

    @staticmethod
    def get_metrics() -> PerformanceMetrics:
        if not hasattr(_local, "metrics"):
            _local.metrics = PerformanceMetrics()
        return _local.metrics

    @staticmethod
    def add_llm_time(ms: float) -> None:
        m = TimingTracker.get_metrics()
        m.llm_execution_ms += max(0.0, float(ms))

    @staticmethod
    def add_duffel_api_time(ms: float) -> None:
        m = TimingTracker.get_metrics()
        m.duffel_api_ms += max(0.0, float(ms))

    @staticmethod
    def add_redis_read_time(ms: float) -> None:
        m = TimingTracker.get_metrics()
        m.redis_read_ms += max(0.0, float(ms))

    @staticmethod
    def add_redis_write_time(ms: float) -> None:
        m = TimingTracker.get_metrics()
        m.redis_write_ms += max(0.0, float(ms))

    @staticmethod
    def add_algorithm_time(ms: float) -> None:
        m = TimingTracker.get_metrics()
        m.algorithm_synthesis_ms += max(0.0, float(ms))
