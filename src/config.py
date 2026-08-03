from __future__ import annotations

from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
import yaml

from src.traces import JsonValue


type NonEmptyString = Annotated[str, Field(min_length=1)]
type PositiveSeconds = Annotated[float, Field(gt=0)]


class VlmConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    model: NonEmptyString
    api_key_env: NonEmptyString
    api_base: NonEmptyString | None = None
    api_base_env: NonEmptyString | None = None
    timeout_seconds: PositiveSeconds = 120.0
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class VlmPlatformsConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    default_platform: NonEmptyString
    platforms: dict[NonEmptyString, VlmConfig]

    @model_validator(mode="after")
    def validate_default_platform(self) -> Self:
        if not self.platforms:
            raise ValueError("Model config defines no VLM platforms")
        if self.default_platform not in self.platforms:
            raise ValueError(
                "default_platform must name a configured VLM platform"
            )
        return self

    def select(self, platform: str | None = None) -> VlmConfig:
        name = platform or self.default_platform
        try:
            return self.platforms[name]
        except KeyError as exc:
            available = ", ".join(sorted(self.platforms))
            raise ValueError(
                f"Unknown VLM platform {name!r}; choose one of: {available}"
            ) from exc


def load_config(path: Path) -> VlmPlatformsConfig:
    """Load VLM platform configuration from YAML."""

    path = Path(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid model config {path}: {exc}") from exc

    try:
        return VlmPlatformsConfig.model_validate(document)
    except ValidationError as exc:
        raise ValueError(f"Invalid model config {path}: {exc}") from exc
