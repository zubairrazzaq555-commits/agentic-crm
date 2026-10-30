"""
Agentic CRM — Provider health tracking and circuit breaker.

Provides:
- HealthStatus enum (HEALTHY, UNHEALTHY, UNAVAILABLE)
- CircuitState enum (CLOSED, OPEN, HALF_OPEN)
- CircuitBreaker — a simple in-process circuit breaker that prevents
  repeatedly selecting a provider that has recently failed.

The circuit breaker is testable independently and does not make any
network calls.  It uses monotonic time for cooldown calculations to
avoid wall-clock surprises.
"""

from __future__ import annotations

import time
from enum import Enum


# ---------------------------------------------------------------------------
# Health status
# ---------------------------------------------------------------------------


class HealthStatus(str, Enum):
    """Provider health states.

    HEALTHY:     The provider is operating normally.
    UNHEALTHY:   The provider has experienced recent failures but may recover.
    UNAVAILABLE: The provider has been explicitly marked as unavailable
                 (e.g. by an administrator, by exceeding failure thresholds,
                 or because the provider is known to be down).
    """

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitState(str, Enum):
    """Circuit breaker states.

    CLOSED:    Normal operation — requests are allowed.
    OPEN:      Provider has exceeded the failure threshold — requests are
               blocked until the cooldown period expires.
    HALF_OPEN: Cooldown has elapsed — one trial request is allowed to
               determine if the provider has recovered.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Simple in-process circuit breaker for a single provider.

    After ``failure_threshold`` consecutive failures the circuit opens.
    While open, the provider is considered temporarily unavailable.
    After ``cooldown_seconds`` the circuit transitions to HALF_OPEN,
    allowing one trial request.  A success in HALF_OPEN closes the
    circuit; a failure reopens it.

    Thread-safety:
        This class is NOT thread-safe.  It is designed for use within
        a single asyncio event loop (single-process).

    Example::

        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)

        # Record failures
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()  # Circuit opens

        assert not cb.is_available  # Provider blocked

        # After cooldown...
        assert cb.is_available  # HALF_OPEN: trial allowed

        cb.record_success()    # Circuit closes again
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        cooldown_seconds: float = 60.0,
    ) -> None:
        """Create a circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening
                               the circuit.  Must be >= 1.
            cooldown_seconds:  Seconds to wait after opening before allowing
                               a trial request.  Must be > 0.

        Raises:
            ValueError: If failure_threshold < 1 or cooldown_seconds <= 0.
        """
        if failure_threshold < 1:
            raise ValueError(
                f"failure_threshold must be >= 1, got {failure_threshold}"
            )
        if cooldown_seconds <= 0:
            raise ValueError(
                f"cooldown_seconds must be > 0, got {cooldown_seconds}"
            )

        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds

        # Internal state
        self._consecutive_failures: int = 0
        self._state: CircuitState = CircuitState.CLOSED
        self._opened_at: float | None = None  # monotonic timestamp

    # -- Public properties ---------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """The current circuit state, accounting for cooldown expiry."""
        self._check_half_open()
        return self._state

    @property
    def failure_threshold(self) -> int:
        """Number of consecutive failures needed to open the circuit."""
        return self._failure_threshold

    @property
    def cooldown_seconds(self) -> float:
        """Seconds the circuit remains open before transitioning to HALF_OPEN."""
        return self._cooldown_seconds

    @property
    def consecutive_failures(self) -> int:
        """Current count of consecutive failures."""
        return self._consecutive_failures

    @property
    def is_available(self) -> bool:
        """Whether the circuit allows requests (CLOSED or HALF_OPEN)."""
        self._check_half_open()
        return self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    # -- Recording outcomes --------------------------------------------------

    def record_success(self) -> None:
        """Record a successful provider call.

        Resets the failure counter and closes the circuit.
        """
        self._consecutive_failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def record_failure(self) -> None:
        """Record a failed provider call.

        Increments the consecutive failure counter.  If the threshold is
        reached, opens the circuit.  If the circuit was HALF_OPEN (a trial
        request failed), it reopens.
        """
        self._consecutive_failures += 1

        if self._state == CircuitState.HALF_OPEN:
            # Trial request failed — reopen the circuit
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
        elif self._consecutive_failures >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()

    def reset(self) -> None:
        """Reset the circuit breaker to its initial (CLOSED) state.

        Useful for administrative recovery or testing.
        """
        self._consecutive_failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    # -- Internal ------------------------------------------------------------

    def _check_half_open(self) -> None:
        """Transition OPEN → HALF_OPEN if the cooldown has elapsed."""
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self._cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
