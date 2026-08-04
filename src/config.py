from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
import yaml

from src.traces import JsonValue


type NonEmptyString = Annotated[str, Field(min_length=1)]
type PositiveSeconds = Annotated[float, Field(gt=0)]
type UnitInterval = Annotated[float, Field(ge=0, le=1)]
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


class StageModelConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    platform: NonEmptyString
    reasoning: ReasoningConfig = Field(default_factory=ReasoningConfig)


class StageModelsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detection: StageModelConfig
    road_region: StageModelConfig
    relations: StageModelConfig
    weather: StageModelConfig


class VlmConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    model: NonEmptyString
    api_base: NonEmptyString
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class ObjectDetectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_object_area_ratio: UnitInterval = 0.0


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    object_detection: ObjectDetectionConfig = Field(
        default_factory=ObjectDetectionConfig
    )


class VlmPlatformsConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    timeout_seconds: PositiveSeconds = 120.0
    max_tokens: Annotated[int, Field(gt=0)]
    stages: StageModelsConfig
    platforms: dict[NonEmptyString, VlmConfig]

    @model_validator(mode="after")
    def validate_stage_platforms(self) -> Self:
        if not self.platforms:
            raise ValueError("Model config defines no VLM platforms")
        for stage_name, stage in self.stages:
            if stage.platform not in self.platforms:
                raise ValueError(
                    f"Stage {stage_name!r} names unknown VLM platform "
                    f"{stage.platform!r}"
                )
        return self

    def select(self, stage: StageModelConfig) -> VlmConfig:
        return self.platforms[stage.platform]


def load_app_config(path: Path) -> AppConfig:
    """Load pipeline behavior configuration from YAML."""

    return _load_yaml_config(path, AppConfig, name="application")


def load_model_config(path: Path) -> VlmPlatformsConfig:
    """Load VLM platform configuration from YAML."""

    return _load_yaml_config(path, VlmPlatformsConfig, name="model")


def _load_yaml_config[T: BaseModel](
    path: Path,
    model: type[T],
    *,
    name: str,
) -> T:
    path = Path(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid {name} config {path}: {exc}") from exc

    try:
        return model.model_validate(document)
    except ValidationError as exc:
        raise ValueError(f"Invalid {name} config {path}: {exc}") from exc
