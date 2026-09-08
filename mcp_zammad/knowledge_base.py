"""Parse Zammad knowledge-base bootstrap assets into a read-only snapshot.

Zammad exposes no flat knowledge-base index. ``POST /knowledge_bases/init`` returns every
knowledge base, category and answer visible to the caller as keyed asset tables. This module
turns that payload into plain dictionaries the MCP layer can expose.
"""

from dataclasses import dataclass, field
from typing import Any


class KnowledgeBaseNotFoundError(LookupError):
    """Raised when a knowledge base, category or answer is not visible to the caller."""


class KnowledgeBaseResponseError(ValueError):
    """Raised when Zammad returns a knowledge-base payload with an unexpected shape."""


@dataclass(frozen=True)
class KnowledgeBaseSnapshot:
    """Visible knowledge-base structure keyed by ID."""

    knowledge_bases: dict[int, dict[str, Any]] = field(default_factory=dict)
    categories: dict[int, dict[str, Any]] = field(default_factory=dict)
    answers: dict[int, dict[str, Any]] = field(default_factory=dict)
    content_ids: dict[int, int | None] = field(default_factory=dict)


def _rows(assets: dict[str, Any], name: str) -> list[dict[str, Any]]:
    """Return the asset rows of one type, sorted by ID.

    Args:
        assets: Asset tables keyed by model name.
        name: Asset model name, e.g. ``KnowledgeBaseCategory``.

    Returns:
        Row dictionaries sorted by ``id``.

    Raises:
        KnowledgeBaseResponseError: If the table or its rows are not dictionaries.
    """
    table = assets.get(name, {})
    if not isinstance(table, dict) or not all(isinstance(row, dict) for row in table.values()):
        raise KnowledgeBaseResponseError(f"Unexpected shape for {name} assets: {type(table).__name__}")
    return sorted(table.values(), key=lambda row: int(row["id"]))


def _titles(rows: list[dict[str, Any]], owner_key: str, primary_locales: set[int]) -> dict[int, dict[str, Any]]:
    """Pick one translation per owner, preferring the primary locale.

    Args:
        rows: Translation rows sorted by ID.
        owner_key: Foreign key naming the translated object.
        primary_locales: Locale IDs flagged as primary.

    Returns:
        Chosen translation row keyed by owner ID.
    """
    chosen: dict[int, dict[str, Any]] = {}
    for row in sorted(rows, key=lambda r: r.get("kb_locale_id") not in primary_locales):
        chosen.setdefault(int(row[owner_key]), row)
    return chosen


def _build_categories(assets: dict[str, Any], primary: set[int]) -> dict[int, dict[str, Any]]:
    """Build category dictionaries with child and answer ID lists."""
    titles = _titles(_rows(assets, "KnowledgeBaseCategoryTranslation"), "category_id", primary)
    categories: dict[int, dict[str, Any]] = {}
    for row in _rows(assets, "KnowledgeBaseCategory"):
        categories[int(row["id"])] = {
            "id": int(row["id"]),
            "knowledge_base_id": int(row["knowledge_base_id"]),
            "parent_id": row.get("parent_id"),
            "title": titles.get(int(row["id"]), {}).get("title", ""),
            "child_category_ids": [],
            "answer_ids": [],
        }
    for category in categories.values():
        parent = categories.get(category["parent_id"]) if category["parent_id"] is not None else None
        if parent is not None:
            parent["child_category_ids"].append(category["id"])
    return categories


def _build_answers(
    assets: dict[str, Any], categories: dict[int, dict[str, Any]], primary: set[int]
) -> tuple[dict[int, dict[str, Any]], dict[int, int | None]]:
    """Build answer dictionaries and remember their primary translation content IDs."""
    titles = _titles(_rows(assets, "KnowledgeBaseAnswerTranslation"), "answer_id", primary)
    answers: dict[int, dict[str, Any]] = {}
    content_ids: dict[int, int | None] = {}
    for row in _rows(assets, "KnowledgeBaseAnswer"):
        answer_id = int(row["id"])
        category = categories[int(row["category_id"])]
        translation = titles.get(answer_id, {})
        answers[answer_id] = {
            "id": answer_id,
            "knowledge_base_id": category["knowledge_base_id"],
            "category_id": category["id"],
            "title": translation.get("title", ""),
            "published_at": row.get("published_at"),
            "internal_at": row.get("internal_at"),
            "archived_at": row.get("archived_at"),
            "promoted": bool(row.get("promoted", False)),
        }
        content_ids[answer_id] = translation.get("content_id")
        category["answer_ids"].append(answer_id)
    return answers, content_ids


def _build_knowledge_bases(
    assets: dict[str, Any], categories: dict[int, dict[str, Any]], answer_count: dict[int, int], primary: set[int]
) -> dict[int, dict[str, Any]]:
    """Build knowledge-base dictionaries with root categories and counts."""
    titles = _titles(_rows(assets, "KnowledgeBaseTranslation"), "knowledge_base_id", primary)
    bases: dict[int, dict[str, Any]] = {}
    for row in _rows(assets, "KnowledgeBase"):
        kb_id = int(row["id"])
        owned = [c for c in categories.values() if c["knowledge_base_id"] == kb_id]
        bases[kb_id] = {
            "id": kb_id,
            "title": titles.get(kb_id, {}).get("title", ""),
            "active": bool(row.get("active", False)),
            "root_category_ids": [c["id"] for c in owned if c["parent_id"] is None],
            "category_count": len(owned),
            "answer_count": answer_count.get(kb_id, 0),
        }
    return bases


def parse_init_assets(payload: Any) -> KnowledgeBaseSnapshot:
    """Parse a ``knowledge_bases/init`` payload into a snapshot.

    Args:
        payload: Decoded JSON returned by ``ZammadAPI.knowledge_bases.init()``.

    Returns:
        Snapshot of every visible knowledge base, category and answer. Empty when the
        caller can see no knowledge base.

    Raises:
        KnowledgeBaseResponseError: If the payload is not the expected asset mapping.
    """
    if not isinstance(payload, dict):
        raise KnowledgeBaseResponseError(f"Expected knowledge-base assets mapping, got {type(payload).__name__}")
    primary = {int(r["id"]) for r in _rows(payload, "KnowledgeBaseLocale") if r.get("primary")}
    categories = _build_categories(payload, primary)
    answers, content_ids = _build_answers(payload, categories, primary)
    answer_count: dict[int, int] = {}
    for answer in answers.values():
        answer_count[answer["knowledge_base_id"]] = answer_count.get(answer["knowledge_base_id"], 0) + 1
    bases = _build_knowledge_bases(payload, categories, answer_count, primary)
    return KnowledgeBaseSnapshot(bases, categories, answers, content_ids)


def extract_answer_body(payload: Any, content_id: int | None) -> str:
    """Extract the answer body from a ``find_answer`` payload.

    Args:
        payload: Decoded JSON returned by ``ZammadAPI.knowledge_bases_answers.find_answer``.
        content_id: Translation content ID that was requested via ``include_contents``.

    Returns:
        The HTML body of the requested translation content.

    Raises:
        KnowledgeBaseResponseError: If the requested content is absent from the payload.
    """
    assets = payload.get("assets") if isinstance(payload, dict) else None
    contents = _rows(assets, "KnowledgeBaseAnswerTranslationContent") if isinstance(assets, dict) else []
    for content in contents:
        if content_id is not None and int(content["id"]) == content_id and "body" in content:
            return str(content["body"])
    raise KnowledgeBaseResponseError(f"Answer payload did not include translation content {content_id}")
