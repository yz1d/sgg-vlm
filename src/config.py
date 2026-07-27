from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

from src.traces import JsonValue


@dataclass(frozen=True, slots=True)
class VlmConfig:
    model: str
    api_key_env: str
    api_base: str | None = None
    api_base_env: str | None = None
    timeout_seconds: float = 120.0
    parameters: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RelationExtractionConfig:
    default_platform: str
    platforms: dict[str, VlmConfig]

    def select(self, platform: str | None = None) -> VlmConfig:
        name = platform or self.default_platform
        try:
            return self.platforms[name]
        except KeyError as exc:
            available = ", ".join(sorted(self.platforms))
            raise ValueError(
                f"Unknown relation-extraction platform {name!r}; "
                f"choose one of: {available}"
            ) from exc


@dataclass(frozen=True, slots=True)
class Config:
    relation_extraction: RelationExtractionConfig


def load_config(path: Path) -> Config:
    """Load model-platform configuration from YAML."""

    path = Path(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid model config {path}: {exc}") from exc

    root = _mapping(document, "model config")
    relation = _mapping(root.get("relation_extraction"), "relation_extraction")
    default_platform = _string(
        relation.get("default_platform"),
        "relation_extraction.default_platform",
    )
    platform_values = _mapping(
        relation.get("platforms"), "relation_extraction.platforms"
    )
    if not platform_values:
        raise ValueError("Model config defines no relation-extraction platforms")

    platforms: dict[str, VlmConfig] = {}
    for name, untyped in platform_values.items():
        location = f"relation_extraction.platforms.{name}"
        value = _mapping(untyped, location)
        timeout = value.get("timeout_seconds", 120.0)
        if isinstance(timeout, bool) or not isinstance(timeout, int | float):
            raise ValueError(f"{location}.timeout_seconds must be a number")
        if timeout <= 0:
            raise ValueError(f"{location}.timeout_seconds must be positive")
        api_base = _optional_string(value.get("api_base"), f"{location}.api_base")
        api_base_env = _optional_string(
            value.get("api_base_env"), f"{location}.api_base_env"
        )
        parameters = _json_mapping(
            value.get("parameters", {}), f"{location}.parameters"
        )
        platforms[name] = VlmConfig(
            model=_string(value.get("model"), f"{location}.model"),
            api_key_env=_string(
                value.get("api_key_env"), f"{location}.api_key_env"
            ),
            api_base=api_base,
            api_base_env=api_base_env,
            timeout_seconds=float(timeout),
            parameters=parameters,
        )

    if default_platform not in platforms:
        raise ValueError(
            "relation_extraction.default_platform must name a configured platform"
        )
    return Config(
        relation_extraction=RelationExtractionConfig(
            default_platform=default_platform,
            platforms=platforms,
        )
    )


def _mapping(value: object, location: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"{location} must be a table")
    return cast(dict[str, Any], value)


def _string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} must be a nonempty string")
    return value.strip()


def _optional_string(value: object, location: str) -> str | None:
    if value is None:
        return None
    return _string(value, location)


def _json_mapping(value: object, location: str) -> dict[str, JsonValue]:
    mapping = _mapping(value, location)
    return {
        key: _json_value(item, f"{location}.{key}")
        for key, item in mapping.items()
    }


def _json_value(value: object, location: str) -> JsonValue:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list):
        return [
            _json_value(item, f"{location}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {
            str(key): _json_value(item, f"{location}.{key}")
            for key, item in value.items()
        }
    raise ValueError(f"{location} must contain only JSON-compatible values")
