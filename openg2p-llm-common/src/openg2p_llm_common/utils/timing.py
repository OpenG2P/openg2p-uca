import asyncio
import functools
import logging
import time
from typing import Any, Callable

from ..config import Settings

_config = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


def time_it(func_name: str | None = None) -> Callable:
    """
    Decorator to measure and log execution time of functions.

    Args:
        func_name: Optional custom name for logging. If not provided, uses the function's __name__

    Returns:
        Decorated function that logs execution time

    Usage:
        @time_it("MyFunction")
        async def my_function():
            pass

        @time_it()  # Uses function name automatically
        def sync_function():
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.perf_counter() - start
                if _config.enable_time_it_log:
                    _logger.info(f"{func_name or func.__name__} took {duration:.3f}s")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.perf_counter() - start
                if _config.enable_time_it_log:
                    _logger.info(f"{func_name or func.__name__} took {duration:.3f}s")

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
