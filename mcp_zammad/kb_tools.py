"""Register the read-only knowledge-base MCP tools and resources.

Failures from the client (HTTP errors, not-found, malformed payloads) propagate so FastMCP
reports them as tool/resource errors instead of success-shaped strings.
"""

from collections.abc import Callable

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import kb_docs as docs
from . import kb_format as fmt
from .client import ZammadClient
from .kb_models import (
    GetKbAnswerParams,
    GetKbCategoryParams,
    GetKnowledgeBaseParams,
    KnowledgeBase,
    KnowledgeBaseAnswer,
    KnowledgeBaseCategory,
    ListKbAnswersParams,
    ListKnowledgeBasesParams,
    SearchKbAnswersParams,
)
from .models import ResponseFormat

ClientFactory = Callable[[], ZammadClient]
Truncate = Callable[[str], str]
Annotate = Callable[[str], ToolAnnotations]


def register_knowledge_base_tools(
    mcp: FastMCP, get_client: ClientFactory, truncate: Truncate, read_only: Annotate
) -> None:
    """Register read-only knowledge-base tools on ``mcp``.

    Args:
        mcp: FastMCP server to register on.
        get_client: Supplies the Zammad client capability.
        truncate: Bounds response size at the MCP boundary.
        read_only: Builds read-only tool annotations from a title.
    """
    _register_structure_tools(mcp, get_client, truncate, read_only)
    _register_answer_tools(mcp, get_client, truncate, read_only)


def _register_structure_tools(mcp: FastMCP, get_client: ClientFactory, truncate: Truncate, read_only: Annotate) -> None:
    """Register knowledge-base and category lookup tools."""

    @mcp.tool(annotations=read_only("List Knowledge Bases"), description=docs.LIST_KNOWLEDGE_BASES)
    def zammad_list_knowledge_bases(params: ListKnowledgeBasesParams) -> str:
        kbs = [KnowledgeBase(**kb) for kb in get_client().list_knowledge_bases()]
        return truncate(fmt.render_list(kbs, params.response_format, fmt.knowledge_bases_markdown))

    @mcp.tool(annotations=read_only("Get Knowledge Base"), description=docs.GET_KNOWLEDGE_BASE)
    def zammad_get_knowledge_base(params: GetKnowledgeBaseParams) -> str:
        kb = KnowledgeBase(**get_client().get_knowledge_base(params.kb_id))
        return truncate(fmt.render_one(kb, params.response_format, fmt.knowledge_base_markdown))

    @mcp.tool(annotations=read_only("Get Knowledge Base Category"), description=docs.GET_KB_CATEGORY)
    def zammad_get_kb_category(params: GetKbCategoryParams) -> str:
        category = KnowledgeBaseCategory(**get_client().get_kb_category(params.kb_id, params.category_id))
        return truncate(fmt.render_one(category, params.response_format, fmt.category_markdown))


def _register_answer_tools(mcp: FastMCP, get_client: ClientFactory, truncate: Truncate, read_only: Annotate) -> None:
    """Register answer listing, search and retrieval tools."""

    @mcp.tool(annotations=read_only("List Knowledge Base Answers"), description=docs.LIST_KB_ANSWERS)
    def zammad_list_kb_answers(params: ListKbAnswersParams) -> str:
        raw = get_client().list_kb_answers(params.kb_id, category_id=params.category_id)
        answers = [KnowledgeBaseAnswer(**a) for a in raw]
        return truncate(fmt.render_list(answers, params.response_format, fmt.answers_markdown))

    @mcp.tool(annotations=read_only("Search Knowledge Base Answers"), description=docs.SEARCH_KB_ANSWERS)
    def zammad_search_kb_answers(params: SearchKbAnswersParams) -> str:
        answers = [KnowledgeBaseAnswer(**a) for a in get_client().search_kb_answers(params.kb_id, params.query)]
        return truncate(fmt.render_list(answers, params.response_format, fmt.answers_markdown))

    @mcp.tool(annotations=read_only("Get Knowledge Base Answer"), description=docs.GET_KB_ANSWER)
    def zammad_get_kb_answer(params: GetKbAnswerParams) -> str:
        answer = KnowledgeBaseAnswer(**get_client().get_kb_answer(params.kb_id, params.answer_id))
        return truncate(fmt.render_one(answer, params.response_format, fmt.answer_markdown))


def register_knowledge_base_resources(mcp: FastMCP, get_client: ClientFactory, truncate: Truncate) -> None:
    """Register ``zammad://kb/...`` resources on ``mcp``.

    Args:
        mcp: FastMCP server to register on.
        get_client: Supplies the Zammad client capability.
        truncate: Bounds response size at the MCP boundary.
    """

    @mcp.resource("zammad://kb/{kb_id}")
    def get_kb_resource(kb_id: str) -> str:
        """Get a knowledge base as a resource."""
        kb = KnowledgeBase(**get_client().get_knowledge_base(int(kb_id)))
        return truncate(fmt.render_one(kb, ResponseFormat.MARKDOWN, fmt.knowledge_base_markdown))

    @mcp.resource("zammad://kb/{kb_id}/category/{category_id}")
    def get_kb_category_resource(kb_id: str, category_id: str) -> str:
        """Get a knowledge-base category as a resource."""
        category = KnowledgeBaseCategory(**get_client().get_kb_category(int(kb_id), int(category_id)))
        return truncate(fmt.render_one(category, ResponseFormat.MARKDOWN, fmt.category_markdown))

    @mcp.resource("zammad://kb/{kb_id}/answer/{answer_id}")
    def get_kb_answer_resource(kb_id: str, answer_id: str) -> str:
        """Get a knowledge-base answer with body as a resource."""
        answer = KnowledgeBaseAnswer(**get_client().get_kb_answer(int(kb_id), int(answer_id)))
        return truncate(fmt.render_one(answer, ResponseFormat.MARKDOWN, fmt.answer_markdown))
