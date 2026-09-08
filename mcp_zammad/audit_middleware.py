"""FastMCP middleware that audits every tool invocation."""

import time

import mcp.types as mt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import ToolResult

from .audit import AuditLogger, error_details


class AuditMiddleware(Middleware):
    """Record one ``tool_call`` audit event per MCP tool invocation."""

    def __init__(self, audit: AuditLogger) -> None:
        """Bind the middleware to an audit sink.

        Args:
            audit: Logger that receives the ``tool_call`` records.
        """
        self._audit = audit

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        """Invoke the tool once, then audit its outcome without capturing arguments or results.

        Args:
            context: FastMCP middleware context carrying the tool-call request.
            call_next: Continuation that executes the remaining pipeline and the tool.

        Returns:
            The tool result, unchanged.

        Raises:
            BaseException: Whatever the tool raised, re-raised after the failure is recorded.
        """
        started = time.monotonic()
        try:
            result = await call_next(context)
        except BaseException as exc:
            self._log(context.message.name, started, success=False, details=error_details(exc))
            raise
        self._log(context.message.name, started, success=True)
        return result

    def _log(self, tool: str, started: float, *, success: bool, details: dict[str, str] | None = None) -> None:
        """Emit a ``tool_call`` record with the elapsed time since ``started``.

        Args:
            tool: Name of the invoked tool.
            started: ``time.monotonic()`` reading taken before the call.
            success: Whether the tool returned normally.
            details: Optional. Failure description from ``error_details``.
        """
        elapsed_ms = round((time.monotonic() - started) * 1000, 3)
        self._audit.log_event("tool_call", tool, success=success, duration_ms=elapsed_ms, details=details)
