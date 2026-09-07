"""
Expose Pydantic parameter models as flat MCP tool arguments.

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
from collections.abc import Callable
from typing import Annotated, Any, TypeVar

from pydantic import BaseModel
from pydantic.fields import FieldInfo

M = TypeVar("M", bound=BaseModel)
R = TypeVar("R")


def flat_params(model: type[M]) -> Callable[[Callable[[M], R]], Callable[..., R]]:
    """
    Expose ``model``'s fields as keyword-only tool arguments.

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
        @functools.wraps(fn)
        def wrapper(**kwargs: Any) -> R:
            return fn(model(**kwargs))

        signature = _flat_signature(model, inspect.signature(fn).return_annotation)
        wrapper.__signature__ = signature  # type: ignore[attr-defined]
        wrapper.__annotations__ = {name: param.annotation for name, param in signature.parameters.items()}
        wrapper.__annotations__["return"] = signature.return_annotation
        return wrapper

    return decorator


def _flat_signature(model: type[BaseModel], return_annotation: Any) -> inspect.Signature:
    """
    Build a signature with one keyword-only parameter per model field.

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
    """
    Convert a model field into a keyword-only parameter.

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
