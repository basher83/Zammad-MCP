"""Expose Pydantic parameter models as flat MCP tool arguments.

FastMCP derives a tool's ``inputSchema`` from the function signature. A tool
declared as ``def tool(params: Model)`` therefore advertises a single nested
``params`` object, while MCP clients send arguments as a flat dictionary.
``flat_params`` rewrites the advertised signature so every model field becomes
a keyword-only argument, then rebuilds the model before calling the tool body
so ``Field`` constraints, ``extra="forbid"``, and model validators still apply.
"""

import copy
import functools
import inspect
import os
from collections.abc import Callable
from typing import Annotated, Any, Literal, TypeVar

from pydantic import BaseModel, Field, field_validator
from pydantic.fields import FieldInfo

from .models import StrictBaseModel

M = TypeVar("M", bound=BaseModel)
R = TypeVar("R")


def flat_params(model: type[M]) -> Callable[[Callable[[M], R]], Callable[..., R]]:
    """Expose ``model``'s fields as keyword-only tool arguments.

    Parameters
    ----------
    model : type[M]
        The Pydantic model the decorated tool accepts as its sole ``params`` argument.

    Returns
    -------
    Callable[[Callable[[M], R]], Callable[..., R]]
        A decorator that wraps the tool so FastMCP sees one argument per model field.

    """

    def decorator(fn: Callable[[M], R]) -> Callable[..., R]:
        """Wrap ``fn`` so it is registered with one keyword argument per model field."""

        @functools.wraps(fn)
        def wrapper(**kwargs: Any) -> R:
            """Rebuild the model from flat keyword arguments and call the tool body."""
            return fn(model(**kwargs))

        signature = _flat_signature(model, inspect.signature(fn).return_annotation)
        wrapper.__signature__ = signature  # type: ignore[attr-defined]
        wrapper.__annotations__ = {name: param.annotation for name, param in signature.parameters.items()}
        wrapper.__annotations__["return"] = signature.return_annotation
        return wrapper

    return decorator


def _flat_signature(model: type[BaseModel], return_annotation: Any) -> inspect.Signature:
    """Build a signature with one keyword-only parameter per model field.

    Parameters
    ----------
    model : type[BaseModel]
        The Pydantic model whose fields become parameters.
    return_annotation : Any
        The wrapped tool's return annotation.

    Returns
    -------
    inspect.Signature
        A signature FastMCP can introspect to produce a flat ``inputSchema``.

    """
    parameters = [_field_parameter(name, field) for name, field in model.model_fields.items()]
    return inspect.Signature(parameters, return_annotation=return_annotation)


def _field_parameter(name: str, field: FieldInfo) -> inspect.Parameter:
    """Convert a model field into a keyword-only parameter.

    Parameters
    ----------
    name : str
        The model field name.
    field : FieldInfo
        The field constraints and default.

    Returns
    -------
    inspect.Parameter
        The parameter exposed under the Python field name.

    """
    info = copy.copy(field)
    info.alias = None
    info.validation_alias = None
    info.serialization_alias = None
    info.alias_priority = None
    default = inspect.Parameter.empty if field.is_required() else field.get_default(call_default_factory=True)
    return inspect.Parameter(
        name,
        inspect.Parameter.KEYWORD_ONLY,
        default=default,
        annotation=Annotated[field.annotation, info],
    )


# ---------------------------------------------------------------------------
# Draft-only tool parameters. None of these models describes a send or a
# ticket/article creation.
# ---------------------------------------------------------------------------

MAX_DRAFT_ATTACHMENTS = 10


def _absolute_paths(paths: list[str]) -> list[str]:
    """Reject relative attachment paths; the server reads local files and must not guess a directory."""
    for path in paths:
        if not os.path.isabs(path):
            msg = f"attachment path must be absolute: {path}"
            raise ValueError(msg)
    return paths


class _TicketIdParams(StrictBaseModel):
    ticket_id: int = Field(gt=0, description="Internal ticket ID (NOT the display number)")


class TicketSharedDraftGetParams(_TicketIdParams):
    """Parameters for reading the shared draft of a ticket."""


class TicketSharedDraftDeleteParams(_TicketIdParams):
    """Parameters for deleting the shared draft of a ticket."""


class TicketSharedDraftWriteParams(_TicketIdParams):
    """Parameters for saving (replacing) the shared draft of a ticket. Never sends."""

    body: str = Field(min_length=1, description="Draft text")
    content_type: Literal["text/html", "text/plain"] = Field(
        default="text/plain", description="text/plain is escaped to HTML before it is stored"
    )
    type: Literal["email", "note"] = Field(default="email", description="Article type of the reply form")
    internal: bool = Field(default=False, description="Internal note (agents only)")
    to: str | None = Field(default=None, description="Recipient(s) for an email draft")
    cc: str | None = Field(default=None, description="CC recipient(s)")
    subject: str | None = Field(default=None, description="Subject for an email draft")
    attachments: list[str] = Field(
        default=[],
        max_length=MAX_DRAFT_ATTACHMENTS,
        description="Absolute paths inside ZAMMAD_ATTACHMENT_DIR (size-capped); each is uploaded to Zammad's upload cache first",
    )

    _check_paths = field_validator("attachments")(_absolute_paths)


class NewTicketDraftListParams(StrictBaseModel):
    """Parameters for listing new-ticket shared drafts."""

    group: str | None = Field(default=None, description="Group name or ID; only drafts of this group")


class NewTicketDraftIdParams(StrictBaseModel):
    """Parameters for reading or deleting one new-ticket shared draft."""

    draft_id: int = Field(gt=0, description="Shared draft ID")


class NewTicketDraftWriteParams(StrictBaseModel):
    """Parameters for saving a shared draft on the new-ticket screen. Never creates a ticket."""

    name: str = Field(min_length=1, description="Draft name shown in the draft list")
    group: str = Field(min_length=1, description="Group name or ID")
    title: str | None = Field(default=None, description="Ticket title")
    customer: str | None = Field(default=None, description="Customer email or user ID")
    to: str | None = Field(default=None, description="Recipient(s) for an email-out draft")
    cc: str | None = Field(default=None, description="CC recipient(s)")
    subject: str | None = Field(default=None, description="Article subject")
    body: str | None = Field(default=None, description="Article text")
    content_type: Literal["text/html", "text/plain"] = Field(
        default="text/plain", description="text/plain is escaped to HTML before it is stored"
    )
    article_type: Literal["email-out", "phone-in", "note"] = Field(
        default="email-out", description="Kind of ticket the form is set to (the form's sender type)"
    )
    attachments: list[str] = Field(
        default=[],
        max_length=MAX_DRAFT_ATTACHMENTS,
        description="Absolute paths inside ZAMMAD_ATTACHMENT_DIR (size-capped); each is uploaded to Zammad's upload cache first",
    )
    draft_id: int | None = Field(default=None, gt=0, description="Update this draft instead of creating one")

    _check_paths = field_validator("attachments")(_absolute_paths)


class ReplyInProgressGetParams(_TicketIdParams):
    """Parameters for reading the reply in progress of the current user."""


class ReplyInProgressSaveParams(_TicketIdParams):
    """Parameters for writing the reply in progress (taskbar draft) of the current user. Never sends."""

    body: str = Field(min_length=1, description="Reply text")
    content_type: Literal["text/html", "text/plain"] = Field(
        default="text/plain", description="text/plain is escaped to HTML before it is stored"
    )
    to: str | None = Field(default=None, description="Recipient(s)")
    cc: str | None = Field(default=None, description="CC recipient(s)")
    subject: str | None = Field(default=None, description="Subject")
    type: Literal["email", "note"] | None = Field(
        default=None, description="Article type; kept from the existing reply box when omitted (a new one is email)"
    )
    internal: bool | None = Field(
        default=None,
        description="Internal note flag; kept from the existing reply box when omitted (a new one is false)",
    )
    reply_to_article_id: int | None = Field(
        default=None,
        gt=0,
        description="Email article this reply answers; to, cc, subject and threading are filled from it. "
        "Omitted: the latest customer email of the ticket",
    )
    attachments: list[str] = Field(
        default=[],
        max_length=MAX_DRAFT_ATTACHMENTS,
        description="Absolute paths inside ZAMMAD_ATTACHMENT_DIR (size-capped); uploaded first, then added to the reply box",
    )

    _check_paths = field_validator("attachments")(_absolute_paths)
