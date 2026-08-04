from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
import yaml

from src.traces import JsonValue


type NonEmptyString = Annotated[str, Field(min_length=1)]
type PositiveSeconds = Annotated[float, Field(gt=0)]
type ReasoningMode = Literal["default", "disabled", "enabled"]
type ReasoningEffort = Literal[
    "minimal", "low", "medium", "high", "xhigh", "max"
]


class ReasoningConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: ReasoningMode = "default"
    effort: ReasoningEffort | None = None

    @model_validator(mode="after")
    def validate_effort(self) -> Self:
        if self.mode != "enabled" and self.effort is not None:
            raise ValueError("reasoning effort requires mode 'enabled'")
        return self


class ReasoningProfilesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detection: ReasoningConfig = Field(default_factory=ReasoningConfig)
    extraction: ReasoningConfig = Field(default_factory=ReasoningConfig)


class VlmConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    model: NonEmptyString
    api_base: NonEmptyString
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class VlmPlatformsConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    default_platform: NonEmptyString
    timeout_seconds: PositiveSeconds = 120.0
    max_tokens: Annotated[int, Field(gt=0)]
    reasoning: ReasoningProfilesConfig
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

    def select(self) -> VlmConfig:
        return self.platforms[self.default_platform]


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
