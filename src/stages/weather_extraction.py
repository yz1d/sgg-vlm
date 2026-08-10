from __future__ import annotations

import json
from typing import cast

from pydantic import BaseModel, ConfigDict

from src.clients.vlm import VlmClient, VlmRequest
from src.frame import Frame
from src.graph._generated.models import WeatherCondition
from src.stage import StageOutput
from src.stages.vlm_helper import (
    build_original_vlm_image,
    build_request_trace,
    parse_vlm_json,
)
from src.traces import JsonValue, Trace


class WeatherResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weather: WeatherCondition | None


class WeatherExtractionStage:
    """Set one visible weather adjective for the scene."""

    name = "weather-extraction"

    def __init__(self, client: VlmClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        vocabulary = [condition.value for condition in WeatherCondition]
        prompt = _build_prompt(vocabulary)
        stage_input: dict[str, JsonValue] = {"weather": vocabulary}
        response = self.client.complete(
            VlmRequest(
                prompt=prompt,
                images=(build_original_vlm_image(frame),),
                response_schema=cast(
                    dict[str, JsonValue], WeatherResponse.model_json_schema()
                ),
            )
        )
        proposal = WeatherResponse.model_validate(parse_vlm_json(response.text))
        weather = proposal.weather
        normalized_weather = weather.value if weather is not None else None

        return StageOutput(
            weather=weather,
            traces=(
                Trace.text("prompt.txt", prompt),
                Trace.json("stage-input.json", stage_input),
                Trace.json(
                    "request.json",
                    build_request_trace(response, image_roles=("original",)),
                ),
                Trace.json("response.raw.json", response.raw),
                Trace.text("response.txt", response.text),
                Trace.json("weather.json", normalized_weather),
            ),
        )


def _build_prompt(vocabulary: list[str]) -> str:
    return f"""Classify the visible atmospheric condition with one adjective from the vocabulary.
Return null when the image does not show clear evidence.

Vocabulary: {json.dumps(vocabulary, separators=(",", ":"))}
"""
