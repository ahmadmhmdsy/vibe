# services/vibe/src/vibe/api/schemas.py
"""Typed request bodies for the JSON routes.

Every route used to take a raw dict and index it inside the handler, so a
missing or mistyped field surfaced as a KeyError/TypeError -> 500 (BE-01).
Declaring the shape here moves that failure to FastAPI's validation, which the
app maps to 400 validation_failed.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ModelRefIn(BaseModel):
    provider_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)


class CreateSessionIn(BaseModel):
    model: ModelRefIn


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


class SystemPromptIn(BaseModel):
    """PATCH /settings body (BE-19's GUI half).

    A blank string is not an error: it clears the saved override so the built-in
    default applies again. A missing or mistyped field is a 400 through the shared
    validation handler rather than a 500 from a KeyError.
    """

    # Required on purpose: a body that forgot the key would otherwise clear the
    # user's saved prompt - a silent, destructive default.
    system_prompt: str = Field(max_length=20_000)
