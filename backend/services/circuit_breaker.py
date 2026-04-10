"""
backend/services/circuit_breaker.py
-------------------------------------
Generic circuit breaker for LLM and scraper calls.

States:  CLOSED (normal) → OPEN (blocking) → HALF_OPEN (testing)
"""
import time
import asyncio
import functools
import logging
from enum import Enum
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CBState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    A per-service circuit breaker.

    Usage:
        cb = CircuitBreaker("lm_studio", fail_max=3, reset_timeout=60)

        async with cb:
            result = await call_lm_studio(...)
    """

    def __init__(self, name: str, fail_max: int = 3, reset_timeout: float = 60.0):
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout

        self._state = CBState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CBState:
        if self._state == CBState.OPEN:
            if time.monotonic() - (self._last_failure_time or 0) >= self.reset_timeout:
                logger.info(f"[CB:{self.name}] Reset timeout elapsed — HALF_OPEN")
                self._state = CBState.HALF_OPEN
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state == CBState.OPEN

    async def __aenter__(self):
        async with self._lock:
            if self.state == CBState.OPEN:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker [{self.name}] is OPEN — service unavailable"
                )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            if exc_type is None:
                # Success — reset
                if self._state == CBState.HALF_OPEN:
                    logger.info(f"[CB:{self.name}] Probe succeeded — CLOSED")
                self._state = CBState.CLOSED
                self._failure_count = 0
                self._last_failure_time = None
            elif exc_type is not CircuitBreakerOpenError:
                # Real failure
                self._failure_count += 1
                self._last_failure_time = time.monotonic()
                logger.warning(
                    f"[CB:{self.name}] Failure {self._failure_count}/{self.fail_max}"
                )
                if self._failure_count >= self.fail_max:
                    self._state = CBState.OPEN
                    logger.error(f"[CB:{self.name}] OPEN — too many failures")
        return False  # do not suppress exceptions

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "fail_max": self.fail_max,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when a call is blocked because the circuit is OPEN."""
    pass


# ── Registry: shared circuit breakers keyed by service name ──────────────────

_registry: Dict[str, CircuitBreaker] = {}


def get_breaker(name: str, fail_max: int = 3, reset_timeout: float = 60.0) -> CircuitBreaker:
    """Get or create a named circuit breaker."""
    if name not in _registry:
        _registry[name] = CircuitBreaker(name, fail_max=fail_max, reset_timeout=reset_timeout)
    return _registry[name]


def all_breaker_statuses() -> list:
    return [cb.get_status() for cb in _registry.values()]
