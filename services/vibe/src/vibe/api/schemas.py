# services/vibe/src/vibe/api/schemas.py
"""Typed request bodies for the JSON routes.

Every route used to take a raw dict and index it inside the handler, so a
missing or mistyped field surfaced as a KeyError/TypeError -> 500 (BE-01).
Declaring the shape here moves that failure to FastAPI's validation, which the
app maps to 400 validation_failed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ModelRefIn(BaseModel):
    provider_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)


class ProjectSourceIn(BaseModel):
    """Where the new session's project comes from (M8/C1).

    Optional and defaulted, so a client that only knows about `model` -- every
    client before this one -- creates exactly the session it always did. `path`
    is for a folder import and `url` for a git one; which of the two is required
    is a rule about the kind, so it is enforced where the kind becomes a
    provider rather than duplicated in a validator here.
    """

    kind: Literal["empty", "template", "folder", "git"] = "empty"
    path: str | None = None
    url: str | None = None


class CreateSessionIn(BaseModel):
    model: ModelRefIn
    source: ProjectSourceIn = Field(default_factory=ProjectSourceIn)


class UpdateSessionIn(BaseModel):
    title: str | None = None
    model: ModelRefIn | None = None


class AttachmentIn(BaseModel):
    name: str
    content_type: str
    data_base64: str


class SendMessageIn(BaseModel):
    content: str = Field(min_length=1)
    attachments: list[AttachmentIn] = Field(default_factory=list)


class WriteFileIn(BaseModel):
    content: str


class CommitIn(BaseModel):
    """POST /sessions/{sid}/vcs/commit (M8/C2).

    The message is required and non-empty: an empty one would make git open an
    editor, which in a server process means a command that never returns.
    """

    message: str = Field(min_length=1, max_length=10_000)


class BranchIn(BaseModel):
    """POST /sessions/{sid}/vcs/branch. `create` is what separates a new branch
    from a switch to one that exists; the Name is validated against git's rules
    where it is used."""

    name: str = Field(min_length=1, max_length=200)
    create: bool = False


class SystemPromptIn(BaseModel):
    """PATCH /settings body (BE-19's GUI half).

    A blank string is not an error: it clears the saved override so the built-in
    default applies again. A missing or mistyped field is a 400 through the shared
    validation handler rather than a 500 from a KeyError.
    """

    # Required on purpose: a body that forgot the key would otherwise clear the
    # user's saved prompt - a silent, destructive default.
    system_prompt: str = Field(max_length=20_000)
