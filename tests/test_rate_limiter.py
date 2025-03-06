"""Tests for the rate limiter utility."""

import time
from unittest.mock import patch

from app.utils.rate_limiter import RateLimiter, rate_limited


class TestRateLimiter:
    """Test cases for the RateLimiter class."""

    def test_init(self):
        """Test initialization of RateLimiter."""
        limiter = RateLimiter(max_calls=10, period=60.0)
        assert limiter.max_calls == 10
        assert limiter.period == 60.0
        assert len(limiter.calls) == 0

    def test_cleanup_old_calls(self):
        """Test cleaning up old calls outside the time window."""
        limiter = RateLimiter(max_calls=5, period=10.0)

        # Add some calls with timestamps
        current_time = time.time()
        old_time = current_time - 15.0  # Outside the window

        limiter.calls.append(old_time)
        limiter.calls.append(old_time + 1)
        limiter.calls.append(current_time - 5)  # Inside the window
        limiter.calls.append(current_time - 2)  # Inside the window

        assert len(limiter.calls) == 4

        # Clean up old calls
        limiter._cleanup_old_calls(current_time)

        # Only calls within the window should remain
        assert len(limiter.calls) == 2

    @patch("time.sleep")
    @patch("time.time")
    def test_wait_no_delay_needed(self, mock_time, mock_sleep):
        """Test wait when no delay is needed."""
        mock_time.return_value = 100.0

        limiter = RateLimiter(max_calls=5, period=10.0)
        # Add some calls but not enough to hit the limit
        for i in range(3):
            limiter.calls.append(95.0 + i)

        limiter.wait()

        # Sleep should not be called
        mock_sleep.assert_not_called()
        # A new call should be added
        assert len(limiter.calls) == 4
        assert limiter.calls[-1] == 100.0

    @patch("time.sleep")
    @patch("time.time")
    def test_wait_delay_needed(self, mock_time, mock_sleep):
        """Test wait when delay is needed due to rate limiting."""
        current_time = 100.0
        mock_time.side_effect = [
            current_time,
            current_time + 2.0,
        ]  # First call, then after sleep

        limiter = RateLimiter(max_calls=5, period=10.0)

        # Add enough calls to hit the limit
        for i in range(5):
            limiter.calls.append(95.0 + i)  # Oldest call at 95.0

        # The oldest call is at 95.0, so we need to wait until 105.0
        # That's 5 seconds from our current time of 100.0
        limiter.wait()

        # Sleep should be called with the wait time
        mock_sleep.assert_called_once_with(5.0)

        # After waiting, a new call should be added
        assert len(limiter.calls) == 6
        assert limiter.calls[-1] == 102.0  # current_time + 2.0

    @patch("time.sleep")
    @patch("time.time")
    def test_wait_max_wait_time(self, mock_time, mock_sleep):
        """Test wait with a very long delay that gets capped."""
        current_time = 100.0
        mock_time.side_effect = [current_time, current_time + 1.0]

        limiter = RateLimiter(max_calls=2, period=120.0)  # 2 minute period

        # Add calls that would require waiting more than MAX_REQUEST_WAIT_TIME
        limiter.calls.append(50.0)  # This would require waiting 70 seconds
        limiter.calls.append(51.0)

        limiter.wait()

        # Sleep should be called with MAX_REQUEST_WAIT_TIME (60 seconds)
        mock_sleep.assert_called_once_with(60.0)


class TestRateLimitedDecorator:
    """Test cases for the rate_limited decorator."""

    @patch("app.utils.rate_limiter.RateLimiter.wait")
    def test_rate_limited_decorator(self, mock_wait):
        """Test that the decorator applies rate limiting."""

        @rate_limited(max_calls=10, period=60.0)
        def test_function(x, y):
            return x + y

        # Call the decorated function
        result = test_function(5, 7)

        # The wait method should be called
        mock_wait.assert_called_once()

        # The function should execute normally
        assert result == 12

    @patch("app.utils.rate_limiter.RateLimiter.wait")
    def test_rate_limited_with_defaults(self, mock_wait):
        """Test the decorator with default values."""

        @rate_limited(max_calls=5)  # Default period is 60.0
        def test_function():
            return "test"

        result = test_function()

        mock_wait.assert_called_once()
        assert result == "test"

    @patch("time.sleep")
    @patch("time.time")
    def test_rate_limited_integration(self, mock_time, mock_sleep):
        """Test the decorator with actual rate limiting."""
        # Set up time mock to simulate passing time
        times = [100.0, 100.0, 100.0, 101.0, 101.0]
        mock_time.side_effect = times

        # Create a decorated function with a very strict rate limit
        @rate_limited(max_calls=1, period=10.0)
        def test_function():
            return "test"

        # First call should go through without waiting
        result1 = test_function()
        assert result1 == "test"
        mock_sleep.assert_not_called()

        # Second call should trigger a wait
        result2 = test_function()
        assert result2 == "test"
        mock_sleep.assert_called_once()

        # Verify the sleep duration is correct (10 seconds from the first call)
        args, _ = mock_sleep.call_args
        assert args[0] > 0
