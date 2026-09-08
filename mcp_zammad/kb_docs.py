"""Tool descriptions for the read-only knowledge-base MCP tools."""

from .docstring_templates import format_tool_docstring

_FORMAT_ARG = "Output format: markdown (default) or json"
_KB_ARG = "Knowledge base ID (> 0), from zammad_list_knowledge_bases"
_LIST_SCHEMA = {"items": "list[object]", "count": "int"}
_KB_SCHEMA = {
    "id": "int",
    "title": "str",
    "active": "bool",
    "root_category_ids": "list[int]",
    "category_count": "int",
    "answer_count": "int",
}
_CATEGORY_SCHEMA = {
    "id": "int",
    "knowledge_base_id": "int",
    "parent_id": "int | None",
    "title": "str",
    "child_category_ids": "list[int]",
    "answer_ids": "list[int]",
}
_ANSWER_SCHEMA = {
    "id": "int",
    "knowledge_base_id": "int",
    "category_id": "int",
    "title": "str",
    "published_at": "str | None",
    "internal_at": "str | None",
    "archived_at": "str | None",
    "promoted": "bool",
}
_PROVIDER_ERROR = "Raises a tool error if Zammad rejects the request or returns an unexpected payload"

LIST_KNOWLEDGE_BASES = format_tool_docstring(
    summary="List knowledge bases visible to the current user.",
    args_doc={"response_format": _FORMAT_ARG},
    return_schema=_LIST_SCHEMA,
    examples=[],
    use_when=["'What knowledge bases exist?' -> discover kb_id values for the other KB tools"],
    dont_use_when=["You already know the kb_id (use zammad_get_knowledge_base)"],
    errors=["Reports 'No knowledge bases are visible' when the user can see none", _PROVIDER_ERROR],
)

GET_KNOWLEDGE_BASE = format_tool_docstring(
    summary="Get one knowledge base with its root category IDs and counts.",
    args_doc={"kb_id": _KB_ARG, "response_format": _FORMAT_ARG},
    return_schema=_KB_SCHEMA,
    examples=[],
    use_when=["'Show me knowledge base 1' -> kb_id=1"],
    dont_use_when=["Listing all knowledge bases (use zammad_list_knowledge_bases)"],
    errors=["Raises a tool error if the knowledge base is not visible", _PROVIDER_ERROR],
)

GET_KB_CATEGORY = format_tool_docstring(
    summary="Get one knowledge-base category with its child category IDs and answer IDs.",
    args_doc={"kb_id": _KB_ARG, "category_id": "Category ID (> 0)", "response_format": _FORMAT_ARG},
    return_schema=_CATEGORY_SCHEMA,
    examples=[],
    use_when=["'Browse category 10 in knowledge base 1' -> kb_id=1, category_id=10"],
    dont_use_when=["You need answer bodies (use zammad_get_kb_answer)"],
    errors=["Raises a tool error if the category is not visible in that knowledge base", _PROVIDER_ERROR],
)

LIST_KB_ANSWERS = format_tool_docstring(
    summary="List visible answers in a knowledge base, optionally restricted to one category. Bodies are omitted.",
    args_doc={"kb_id": _KB_ARG, "category_id": "Optional category ID (> 0)", "response_format": _FORMAT_ARG},
    return_schema=_LIST_SCHEMA,
    examples=[],
    use_when=["'What answers are in category 10?' -> kb_id=1, category_id=10"],
    dont_use_when=["Searching by text (use zammad_search_kb_answers)"],
    errors=["Raises a tool error if the category is not visible in that knowledge base", _PROVIDER_ERROR],
)

SEARCH_KB_ANSWERS = format_tool_docstring(
    summary="Find visible answers whose title contains the query (case-insensitive). Bodies are omitted.",
    args_doc={"kb_id": _KB_ARG, "query": "Text to match (1-200 chars)", "response_format": _FORMAT_ARG},
    return_schema=_LIST_SCHEMA,
    examples=[],
    use_when=["'Find the VPN article' -> kb_id=1, query='vpn'"],
    dont_use_when=["You know the answer_id (use zammad_get_kb_answer)"],
    errors=["Reports 'No answers found' when nothing matches", _PROVIDER_ERROR],
)

GET_KB_ANSWER = format_tool_docstring(
    summary="Get one answer including its primary-locale body (HTML as stored in Zammad).",
    args_doc={"kb_id": _KB_ARG, "answer_id": "Answer ID (> 0)", "response_format": _FORMAT_ARG},
    return_schema={**_ANSWER_SCHEMA, "body": "str"},
    examples=[],
    use_when=["'Read answer 100' -> kb_id=1, answer_id=100"],
    dont_use_when=["Listing answers (use zammad_list_kb_answers)"],
    errors=["Raises a tool error if the answer is not visible or its content is missing", _PROVIDER_ERROR],
)
