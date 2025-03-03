"""Rate limiting utilities for API calls."""

import logging
import time
from collections import deque
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# Type variable for generic functions
T = TypeVar("T")

# Constants for rate limiting
MAX_REQUEST_WAIT_TIME = 60  # Maximum time to wait for rate limiting in seconds
BASE_TIME_WINDOW = 60.0  # Base time window in seconds (1 minute)


class RateLimiter:
    """A rate limiter to control the frequency of API calls."""

    def __init__(self, max_calls: int, period: float = BASE_TIME_WINDOW) -> None:
        """
        Initialize the rate limiter.

        Args:
            max_calls: Maximum number of calls allowed in the time period
            period: Time period in seconds (default: 60 seconds)
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()  # Tracks timestamp of calls

    def _cleanup_old_calls(self, current_time: float) -> None:
        """
        Remove calls that are outside the current time window.

        Args:
            current_time: Current timestamp
        """
        # Time window start
        window_start = current_time - self.period

        # Remove calls outside the window
        while self.calls and self.calls[0] < window_start:
            self.calls.popleft()

    def wait(self) -> None:
        """Wait if necessary to comply with the rate limit."""
        current_time = time.time()

        # Clean up old calls
        self._cleanup_old_calls(current_time)

        # Check if we've reached the limit
        if len(self.calls) >= self.max_calls:
            # Calculate how long to wait
            oldest_call = self.calls[0]
            wait_time = oldest_call + self.period - current_time

            if wait_time > 0:
                # Don't wait more than the maximum wait time
                actual_wait = min(wait_time, MAX_REQUEST_WAIT_TIME)
                time.sleep(actual_wait)
                current_time = time.time()  # Update time after sleep

                # Clean up old calls again after waiting
                self._cleanup_old_calls(current_time)

        # Add current call
        self.calls.append(current_time)


# Type for function that takes any arguments and returns type T
FuncT = Callable[..., T]
# Type for decorated function that takes any arguments and returns type T
DecoratedFuncT = Callable[..., T]


def rate_limited(
    max_calls: int, period: float = BASE_TIME_WINDOW
) -> Callable[[FuncT], DecoratedFuncT]:
    """
    Decorator for rate-limiting function calls.

    Args:
        max_calls: Maximum number of calls allowed in the time period
        period: Time period in seconds (default: 60 seconds)

    Returns:
        Decorator function that applies rate limiting
    """
    limiter = RateLimiter(max_calls, period)

    def decorator(func: FuncT) -> DecoratedFuncT:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            limiter.wait()
            return func(*args, **kwargs)

        return wrapper

    return decorator
