"""Preserve valid MIME metadata and recognize common binary signatures."""

import re
from typing import Any

_MAGIC_TYPES = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"PK\x03\x04", "application/zip"),
    (b"PK\x05\x06", "application/zip"),
)


def metadata_mime(item: dict[str, Any]) -> str | None:
    """Read an unambiguous MIME type without changing its spelling.

    Args:
        item: Attachment metadata.

    Returns:
        The supplied MIME type, or None when absent.

    Raises:
        ValueError: If MIME metadata is malformed or conflicting.
    """
    preferences = item.get("preferences")
    if preferences is not None and not isinstance(preferences, dict):
        raise ValueError("Invalid attachment MIME metadata")
    candidates = [item.get(key) for key in ("content_type", "mime-type", "mime_type")]
    candidates.append((preferences or {}).get("Mime-Type"))
    supplied = [value for value in candidates if value is not None and value != ""]
    for value in supplied:
        if not isinstance(value, str) or not re.fullmatch(r"[\w!#$&^.+-]+/[\w!#$&^.+-]+(?:;[ -~]*)?", value, re.ASCII):
            raise ValueError("Invalid attachment MIME metadata")
    if len(set(supplied)) > 1:
        raise ValueError("Conflicting attachment MIME metadata")
    return supplied[0] if supplied else None


def sniff_mime(content: bytes) -> str:
    """Recognize common file signatures without relying on the filename.

    Args:
        content: Downloaded attachment bytes.

    Returns:
        A recognized MIME type, or application/octet-stream.
    """
    return next((mime for signature, mime in _MAGIC_TYPES if content.startswith(signature)), "application/octet-stream")
