"""Shared pytest fixtures and utilities for test suite."""

from collections.abc import Callable
from typing import Any

import pytest


@pytest.fixture
def decorator_capturer():
    """Factory for capturing functions decorated by MCP decorators.

    Returns a function that creates a capture wrapper for any decorator.
    The wrapper intercepts decorated functions and stores them in a dict
    while still calling the original decorator.

    Usage:
        captured, wrapper = decorator_capturer(server.mcp.tool)
        server.mcp.tool = wrapper
        server._setup_tools()
        # Now captured contains all registered tools

    Returns:
        Function that takes an original decorator and returns (captured_dict, wrapper_func)
    """

    def _capture(original_decorator: Callable[..., Any]) -> tuple[dict[str, Any], Callable[..., Any]]:
        """Create a capture wrapper for a decorator.

        Args:
            original_decorator: The original decorator to wrap

        Returns:
            Tuple of (captured functions dict, wrapper decorator)
        """
        captured: dict[str, Any] = {}

        def wrapper(name_or_template: str | None = None, **kwargs: Any) -> Callable[[Callable[..., Any]], Any]:
            """Wrapper decorator that captures the decorated function.

            Args:
                name_or_template: Name or URI template for the decorated function
                **kwargs: Additional keyword arguments for the decorator

            Returns:
                Decorator function
            """

            def decorator(func: Callable[..., Any]) -> Any:
                """Inner decorator that captures and delegates.

                Args:
                    func: Function being decorated

                Returns:
                    Result from original decorator
                """
                # Capture using function name as key, or provided name/template
                key = func.__name__ if name_or_template is None else name_or_template
                captured[key] = func
                # Still call original decorator to maintain normal behavior
                return original_decorator(name_or_template, **kwargs)(func)

            return decorator

        return captured, wrapper

    return _capture
