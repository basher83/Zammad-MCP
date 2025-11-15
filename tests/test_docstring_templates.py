"""Tests for docstring template helpers."""

from mcp_zammad.docstring_templates import format_tool_docstring


def test_format_tool_docstring_includes_all_sections():
    """Docstring template must include Args, Returns, Examples, Errors."""
    doc = format_tool_docstring(
        summary="Search for tickets",
        args_doc={"query": "Search string", "limit": "Maximum results (1-100)"},
        return_schema={"items": "list[Ticket]", "total": "int | None", "count": "int"},
        examples=["Find open tickets: query='state:open'", "Search by number: query='#65003'"],
        errors=["Returns 'No tickets found' if no matches", "Returns 'Error: Rate limit' on 429 status"],
    )

    assert "Args:" in doc
    assert "Returns:" in doc
    assert "Examples:" in doc
    assert "Error Handling:" in doc
    assert "query: Search string" in doc
