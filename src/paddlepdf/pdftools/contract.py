"""Caller-visible contract shared by every PDF tool: spec, outcome, and report."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, JsonValue


class PdfToolError(Exception):
    """Expected, user-facing failure such as bad input, wrong password, or bad range.

    The runner turns it into a failed ``ToolResult``; unexpected exceptions are bugs
    and propagate.
    """


class ToolStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ToolStatus
    tool: str
    output_files: tuple[str, ...] = ()
    data: JsonValue = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    elapsed_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    """What a handler produced; the runner adds status, tool name, and timing."""

    output_files: tuple[str, ...] = ()
    data: JsonValue = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


type ToolHandler = Callable[..., ToolOutcome]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """One agent-callable tool.

    ``handler`` keyword parameters ARE the public schema: annotate each with
    ``Annotated[type, Field(description=...)]``, use ``str`` for paths, and never use
    ``from __future__ import annotations`` in handler modules.
    """

    name: str
    description: str
    handler: ToolHandler
