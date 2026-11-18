"""Resolve existing article attachments without exposing content to MCP clients."""

import base64
from collections.abc import Callable
from typing import Any, TypeVar

from .attachment_metadata import ReferencedAttachment, select_attachments
from .attachment_mime import sniff_mime

T = TypeVar("T")


def reference_call(capability: Callable[..., T], message: str, *args: Any) -> T:
    """Invoke an external capability without disclosing its error payload.

    Args:
        capability: Supplied external operation.
        message: Safe failure description.
        *args: Operation arguments.

    Returns:
        The operation result.

    Raises:
        ValueError: If the external operation fails.
    """
    try:
        return capability(*args)
    except Exception:
        raise ValueError(message) from None


def source_snapshot(
    ticket_id: int, source: int, identifiers: list[int], find: Callable[[int], dict[str, Any]]
) -> tuple[list[ReferencedAttachment], Any]:
    """Read and validate an immutable selection snapshot.

    Args:
        ticket_id: Target ticket ID.
        source: Source article ID.
        identifiers: Selected attachment IDs.
        find: Supplied article lookup capability.

    Returns:
        Validated metadata and source update timestamp.

    Raises:
        ValueError: If source ownership or metadata is invalid.
    """
    article = reference_call(find, "Source article lookup failed", source)
    if not isinstance(article, dict) or type(article.get("id")) is not int or type(article.get("ticket_id")) is not int:
        raise ValueError("Source article metadata is invalid")
    if article["id"] != source or article["ticket_id"] != ticket_id:
        raise ValueError("Source article does not belong to the target ticket")
    return select_attachments(article, identifiers), article.get("updated_at")


def attachment_upload(item: ReferencedAttachment, content: bytes) -> dict[str, str]:
    """Encode a verified download for the Zammad write payload only.

    Args:
        item: Validated attachment metadata.
        content: Downloaded bytes.

    Returns:
        An attachment payload with unchanged filename and bytes.

    Raises:
        ValueError: If the actual length differs from metadata.
    """
    if not isinstance(content, bytes) or len(content) != item.size:
        raise ValueError("Attachment content length differs from its metadata")
    return {
        "filename": item.filename,
        "data": base64.b64encode(content).decode("ascii"),
        "mime-type": item.mime_type or sniff_mime(content),
    }


def resolve_attachments(
    ticket_id: int,
    source_article_id: int,
    attachment_ids: list[int],
    find_article: Callable[[int], dict[str, Any]],
    download: Callable[[int, int, int], bytes],
) -> list[dict[str, str]]:
    """Build verified upload payloads from existing attachments.

    Args:
        ticket_id: Target ticket ID.
        source_article_id: Source article ID.
        attachment_ids: Attachment IDs in requested order.
        find_article: Supplied article lookup capability.
        download: Supplied attachment download capability.

    Returns:
        Attachment upload payloads for the Zammad API only.

    Raises:
        ValueError: If reads, downloads, or validation fail.
    """
    snapshot = source_snapshot(ticket_id, source_article_id, attachment_ids, find_article)
    uploads = [
        attachment_upload(
            item, reference_call(download, "Attachment download failed", ticket_id, source_article_id, item.identifier)
        )
        for item in snapshot[0]
    ]
    if source_snapshot(ticket_id, source_article_id, attachment_ids, find_article) != snapshot:
        raise ValueError("Source article changed while resolving attachments")
    return uploads
