"""Validate server metadata before resolving attachment references."""

from typing import Any, NamedTuple

from .attachment_mime import metadata_mime

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 25 * 1024 * 1024
MAX_SIZE_DIGITS = 10
MAX_FILENAME_LENGTH = 255
ASCII_PRINTABLE_START = 32
CONTROL_RANGE_START = 127
CONTROL_RANGE_END = 159


class ReferencedAttachment(NamedTuple):
    """Keep immutable, validated metadata for a selected attachment."""

    identifier: int
    filename: str
    size: int
    mime_type: str | None


def attachment_size(value: Any) -> int:
    """Parse a nonnegative byte count without lossy coercion.

    Args:
        value: Byte count from the Zammad API.

    Returns:
        Size in bytes.

    Raises:
        ValueError: If the size is invalid or exceeds 10 MiB.
    """
    if isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= MAX_SIZE_DIGITS:
        value = int(value)
    if type(value) is not int or not 0 <= value <= MAX_FILE_BYTES:
        raise ValueError("Attachment size is invalid or exceeds 10 MiB")
    return value


def attachment_filename(value: Any) -> str:
    """Reject unsafe names rather than silently renaming referenced files.

    Args:
        value: Filename from the Zammad API.

    Returns:
        The unchanged safe filename.

    Raises:
        ValueError: If the filename is unsafe.
    """
    if not isinstance(value, str) or not value or value in {".", ".."} or len(value) > MAX_FILENAME_LENGTH:
        raise ValueError("Unsafe attachment filename")
    if any(character in value for character in ("/", "\\", ":")):
        raise ValueError("Unsafe attachment filename")
    if any(
        ord(character) < ASCII_PRINTABLE_START or CONTROL_RANGE_START <= ord(character) <= CONTROL_RANGE_END
        for character in value
    ):
        raise ValueError("Unsafe attachment filename")
    return value


def attachment_index(items: Any) -> dict[int, dict[str, Any]]:
    """Index metadata while rejecting malformed or duplicate identifiers.

    Args:
        items: Attachment metadata returned by Zammad.

    Returns:
        Unique attachment records by ID.

    Raises:
        TypeError: If metadata is not a list.
        ValueError: If records or IDs are malformed.
    """
    if not isinstance(items, list):
        raise TypeError("Invalid source attachment metadata")
    indexed = {}
    for item in items:
        if not isinstance(item, dict) or type(item.get("id")) is not int or item["id"] <= 0:
            raise ValueError("Invalid source attachment ID")
        if item["id"] in indexed:
            raise ValueError("Duplicate source attachment ID")
        indexed[item["id"]] = item
    return indexed


def select_attachments(article: dict[str, Any], identifiers: list[int]) -> list[ReferencedAttachment]:
    """Validate selected attachments in the caller's requested order.

    Args:
        article: Source article metadata.
        identifiers: Requested attachment IDs.

    Returns:
        Validated immutable metadata.

    Raises:
        ValueError: If a reference is absent or total size exceeds 25 MiB.
    """
    try:
        indexed = attachment_index(article.get("attachments"))
    except TypeError:
        raise ValueError("Invalid source attachment metadata") from None
    if any(identifier not in indexed for identifier in identifiers):
        raise ValueError("Referenced attachment is absent from the source article")
    selected = [
        ReferencedAttachment(
            identifier,
            attachment_filename(indexed[identifier].get("filename")),
            attachment_size(indexed[identifier].get("size")),
            metadata_mime(indexed[identifier]),
        )
        for identifier in identifiers
    ]
    if sum(item.size for item in selected) > MAX_TOTAL_BYTES:
        raise ValueError("Referenced attachments exceed 25 MiB in total")
    return selected
