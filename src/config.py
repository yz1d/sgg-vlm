from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.traces import JsonValue


@dataclass(frozen=True, slots=True)
class VlmConfig:
    model: str
    api_key_env: str
    api_base: str | None = None
    timeout_seconds: float = 120.0
    parameters: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Config:
    output_root: Path
    vlm: VlmConfig


def load_config(path: Path) -> Config:
    raise NotImplementedError
