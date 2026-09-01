"""
Thread-safe and context-safe performance timing tracker for Duffel API, LLM, Redis, and Algorithm execution.
"""

from contextvars import ContextVar
from dataclasses import dataclass
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


_current_metrics: ContextVar[PerformanceMetrics] = ContextVar("_current_metrics", default=PerformanceMetrics())


class TimingTracker:
    """Context-safe timing tracker for fine-grained performance breakdown across async/sync tasks."""

    @staticmethod
    def reset() -> None:
        _current_metrics.set(PerformanceMetrics())

    @staticmethod
    def get_metrics() -> PerformanceMetrics:
        try:
            return _current_metrics.get()
        except LookupError:
            m = PerformanceMetrics()
            _current_metrics.set(m)
            return m

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


from contextlib import contextmanager


class StepLogger:
    """Step execution logger tracking start, completion, and total elapsed execution time."""

    @staticmethod
    @contextmanager
    def step(step_num: int, total_steps: int, step_name: str, details: str = ""):
        prefix = f"[STEP {step_num}/{total_steps}]"
        detail_str = f" ({details})" if details else ""
        print(f"\n{prefix} START: {step_name}{detail_str}...", flush=True)
        t0 = time.perf_counter()
        try:
            yield
        finally:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            print(f"{prefix} COMPLETED: {step_name} in {dt_ms:.2f} ms ({dt_ms / 1000.0:.3f}s)", flush=True)

