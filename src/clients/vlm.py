from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.traces import JsonValue


@dataclass(frozen=True, slots=True)
class VlmImage:
    role: str
    data: bytes
    media_type: str


@dataclass(frozen=True, slots=True)
class VlmRequest:
    prompt: str
    images: tuple[VlmImage, ...]
    response_schema: dict[str, JsonValue] | None = None


@dataclass(frozen=True, slots=True)
class VlmResponse:
    text: str
    model: str
    raw: JsonValue | None = None
    request: dict[str, JsonValue] | None = None


class VlmClient(Protocol):
    def complete(self, request: VlmRequest) -> VlmResponse: ...
