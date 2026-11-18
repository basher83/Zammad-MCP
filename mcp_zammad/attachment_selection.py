"""Validate attachment-reference selection at client and MCP boundaries."""

from typing import Annotated, Any

from pydantic import BaseModel, Field, ValidationInfo, ValidatorFunctionWrapHandler

PositiveReferenceID = Annotated[int, Field(strict=True, gt=0)]
MAX_ATTACHMENTS = 10


def validate_reference_ticket(value: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo) -> Any:
    """Preserve raw MCP IDs until model validation can inspect the reference fields.

    Args:
        value: Raw target ticket ID.
        handler: Supplied normal integer validation.
        info: Model data, or no data during FastMCP signature validation.

    Returns:
        The validated ID, or raw input for subsequent model validation.

    Raises:
        ValueError: If references use a nonpositive or noninteger ticket ID.
    """
    if info.data is None:
        return value
    referenced = any(info.data.get(field) is not None for field in ("source_article_id", "attachment_ids"))
    if referenced and (type(value) is not int or value <= 0):
        raise ValueError("Attachment references require strictly positive integer IDs")
    return handler(value)


def validate_selection(source: int | None, identifiers: list[int] | None, inline: Any, ticket_id: int) -> None:
    """Reject incomplete, ambiguous, or unsafe reference selections.

    Args:
        source: Optional. Source article ID.
        identifiers: Optional. Requested attachment IDs.
        inline: Optional. Inline attachment payloads.
        ticket_id: Target ticket ID.

    Raises:
        ValueError: If the reference selection is invalid.
    """
    if source is None and identifiers is None:
        return
    if source is None or identifiers is None:
        raise ValueError("source_article_id and attachment_ids must be provided together")
    if inline is not None:
        raise ValueError("Inline attachments cannot be combined with attachment references")
    if not isinstance(identifiers, list) or not 1 <= len(identifiers) <= MAX_ATTACHMENTS:
        raise ValueError("Select between 1 and 10 attachment IDs")
    if any(type(identifier) is not int or identifier <= 0 for identifier in [ticket_id, source, *identifiers]):
        raise ValueError("Attachment references require strictly positive integer IDs")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Attachment IDs must be unique")


class AttachmentReferenceParams(BaseModel):
    """Declare optional references for article creation."""

    source_article_id: PositiveReferenceID | None = Field(None, description="Source article in the target ticket")
    attachment_ids: list[PositiveReferenceID] | None = Field(
        None,
        min_length=1,
        max_length=10,
        description="Existing attachment IDs in requested order; requires source_article_id",
    )
