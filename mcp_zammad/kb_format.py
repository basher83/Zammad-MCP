"""Render knowledge-base models as markdown or JSON for MCP responses."""

import json
from collections.abc import Callable, Sequence

from pydantic import BaseModel

from .kb_models import KnowledgeBase, KnowledgeBaseAnswer, KnowledgeBaseCategory
from .models import ResponseFormat


def render_one(item: BaseModel, fmt: ResponseFormat, markdown: Callable[..., str]) -> str:
    """Render a single model in the requested format."""
    if fmt == ResponseFormat.JSON:
        return json.dumps(item.model_dump(), indent=2)
    return markdown(item)


def render_list(items: Sequence[BaseModel], fmt: ResponseFormat, markdown: Callable[..., str]) -> str:
    """Render a list of models in the requested format."""
    if fmt == ResponseFormat.JSON:
        return json.dumps({"items": [i.model_dump() for i in items], "count": len(items)}, indent=2)
    return markdown(items)


def _ids(ids: Sequence[int]) -> str:
    return ", ".join(str(i) for i in ids) if ids else "none"


def knowledge_base_markdown(kb: KnowledgeBase) -> str:
    """Format one knowledge base."""
    return "\n".join(
        [
            f"# Knowledge Base: {kb.title} (ID: {kb.id})",
            "",
            f"- Active: {kb.active}",
            f"- Categories: {kb.category_count}",
            f"- Answers: {kb.answer_count}",
            f"- Root category IDs: {_ids(kb.root_category_ids)}",
        ]
    )


def knowledge_bases_markdown(kbs: Sequence[KnowledgeBase]) -> str:
    """Format a knowledge-base list."""
    if not kbs:
        return "No knowledge bases are visible to the current user."
    lines = ["# Knowledge Bases", "", f"Found {len(kbs)} knowledge base(s)", ""]
    lines += [
        f"- **{kb.title}** (ID: {kb.id}) - {kb.category_count} categories, {kb.answer_count} answers" for kb in kbs
    ]
    return "\n".join(lines)


def category_markdown(category: KnowledgeBaseCategory) -> str:
    """Format one category."""
    return "\n".join(
        [
            f"# Category: {category.title} (ID: {category.id})",
            "",
            f"- Knowledge base ID: {category.knowledge_base_id}",
            f"- Parent category ID: {category.parent_id if category.parent_id is not None else 'none (root)'}",
            f"- Child category IDs: {_ids(category.child_category_ids)}",
            f"- Answer IDs: {_ids(category.answer_ids)}",
        ]
    )


def _answer_state(answer: KnowledgeBaseAnswer) -> str:
    if answer.archived_at:
        return "archived"
    if answer.published_at:
        return "published"
    if answer.internal_at:
        return "internal"
    return "draft"


def answers_markdown(answers: Sequence[KnowledgeBaseAnswer]) -> str:
    """Format an answer list."""
    if not answers:
        return "No answers found."
    lines = ["# Knowledge Base Answers", "", f"Found {len(answers)} answer(s)", ""]
    lines += [f"- **{a.title}** (ID: {a.id}, category: {a.category_id}, {_answer_state(a)})" for a in answers]
    return "\n".join(lines)


def answer_markdown(answer: KnowledgeBaseAnswer) -> str:
    """Format one answer including its body."""
    return "\n".join(
        [
            f"# Answer: {answer.title} (ID: {answer.id})",
            "",
            f"- Knowledge base ID: {answer.knowledge_base_id}",
            f"- Category ID: {answer.category_id}",
            f"- State: {_answer_state(answer)}",
            f"- Published at: {answer.published_at or 'never'}",
            f"- Promoted: {answer.promoted}",
            "",
            "## Body",
            "",
            answer.body or "",
        ]
    )
