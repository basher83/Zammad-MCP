"""Shared pytest fixtures and utilities for test suite."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

# Auth env vars that must be cleared so the real .env file doesn't
# interfere with tests that instantiate ZammadMCPServer.
_DOTENV_VARS = (
    # Zammad connection
    "ZAMMAD_URL",
    # Auth vars
    "MCP_AUTH_CLIENT_ID",
    "MCP_AUTH_CLIENT_SECRET",
    "MCP_AUTH_BASE_URL",
    # Transport vars
    "MCP_TRANSPORT",
    "MCP_HOST",
    "MCP_PORT",
    "MCP_SSL_CERTFILE",
    "MCP_SSL_KEYFILE",
)


@pytest.fixture(autouse=True)
def _isolate_from_dotenv(request, monkeypatch):
    """Prevent the real .env file from leaking into tests.

    ZammadMCPServer.__init__ calls _bootstrap_env() which would read the
    developer's .env and pollute the test environment.  We neutralize
    load_dotenv() and also scrub any auth vars that might already be set.
    Tests using the ``dotenv_cwd`` fixture run in an isolated cwd and may
    still load explicitly given .env paths from it.
    """
    real_load_dotenv = load_dotenv

    def _explicit_only(dotenv_path=None, *args, **kwargs):
        if dotenv_path is None:
            return False
        return real_load_dotenv(dotenv_path, *args, **kwargs)

    side_effect = _explicit_only if "dotenv_cwd" in request.fixturenames else None
    with patch("mcp_zammad.server.load_dotenv", side_effect=side_effect):
        for var in _DOTENV_VARS:
            monkeypatch.delenv(var, raising=False)
        yield


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
