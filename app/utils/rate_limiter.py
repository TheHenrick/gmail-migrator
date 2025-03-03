"""
Rate limiting utility for API calls.
"""
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    A rate limiter to control the frequency of API calls.
    """
    
    def __init__(self, max_calls: int, period: float = 60.0):
        """
        Initialize the rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed in the period
            period: Time period in seconds (default: 60 seconds)
        """
        self.max_calls = max_calls
        self.period = period
        self.interval = period / max_calls
        self.last_call_time = 0
        self.call_count = 0
        self.window_start_time = time.time()
    
    def wait(self):
        """
        Wait if necessary to comply with the rate limit.
        """
        current_time = time.time()
        
        # Check if we're in a new window
        if current_time - self.window_start_time > self.period:
            self.window_start_time = current_time
            self.call_count = 0
        
        # If we've made max calls in this window, wait until next window
        if self.call_count >= self.max_calls:
            sleep_time = self.window_start_time + self.period - current_time
            if sleep_time > 0:
                logger.debug(f"Rate limit reached: Sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
                self.window_start_time = time.time()
                self.call_count = 0
        
        # Wait based on interval between calls
        time_since_last_call = current_time - self.last_call_time
        if time_since_last_call < self.interval:
            sleep_time = self.interval - time_since_last_call
            logger.debug(f"Rate limiting: Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_call_time = time.time()
        self.call_count += 1


def rate_limited(max_calls: int, period: float = 60.0):
    """
    Decorator for rate-limiting function calls.
    
    Args:
        max_calls: Maximum number of calls allowed in the period
        period: Time period in seconds (default: 60 seconds)
        
    Returns:
        Decorated function with rate limiting
    """
    limiter = RateLimiter(max_calls, period)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter.wait()
            return func(*args, **kwargs)
        return wrapper
    
    return decorator 