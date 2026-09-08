"""Pydantic contracts for the read-only knowledge-base MCP tools."""

from pydantic import BaseModel, Field

from .models import ResponseFormat, StrictBaseModel

_FORMAT = Field(default=ResponseFormat.MARKDOWN, description="Output format: markdown (default) or json")


class ListKnowledgeBasesParams(StrictBaseModel):
    """List knowledge bases request parameters."""

    response_format: ResponseFormat = _FORMAT


class GetKnowledgeBaseParams(StrictBaseModel):
    """Get knowledge base request parameters."""

    kb_id: int = Field(gt=0, description="Knowledge base ID")
    response_format: ResponseFormat = _FORMAT


class GetKbCategoryParams(StrictBaseModel):
    """Get knowledge-base category request parameters."""

    kb_id: int = Field(gt=0, description="Knowledge base ID")
    category_id: int = Field(gt=0, description="Category ID")
    response_format: ResponseFormat = _FORMAT


class ListKbAnswersParams(StrictBaseModel):
    """List knowledge-base answers request parameters."""

    kb_id: int = Field(gt=0, description="Knowledge base ID")
    category_id: int | None = Field(default=None, gt=0, description="Restrict to one category")
    response_format: ResponseFormat = _FORMAT


class SearchKbAnswersParams(StrictBaseModel):
    """Search knowledge-base answers request parameters."""

    kb_id: int = Field(gt=0, description="Knowledge base ID")
    query: str = Field(min_length=1, max_length=200, description="Case-insensitive text to match in answer titles")
    response_format: ResponseFormat = _FORMAT


class GetKbAnswerParams(StrictBaseModel):
    """Get knowledge-base answer request parameters."""

    kb_id: int = Field(gt=0, description="Knowledge base ID")
    answer_id: int = Field(gt=0, description="Answer ID")
    response_format: ResponseFormat = _FORMAT


class KnowledgeBase(BaseModel):
    """Knowledge base summary."""

    id: int
    title: str
    active: bool
    root_category_ids: list[int]
    category_count: int
    answer_count: int


class KnowledgeBaseCategory(BaseModel):
    """Knowledge-base category with its direct children and answers."""

    id: int
    knowledge_base_id: int
    parent_id: int | None
    title: str
    child_category_ids: list[int]
    answer_ids: list[int]


class KnowledgeBaseAnswer(BaseModel):
    """Knowledge-base answer metadata plus optional body."""

    id: int
    knowledge_base_id: int
    category_id: int
    title: str
    published_at: str | None = None
    internal_at: str | None = None
    archived_at: str | None = None
    promoted: bool = False
    body: str | None = None
