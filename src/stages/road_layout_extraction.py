from __future__ import annotations

import json
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from src.clients.vlm import VlmClient, VlmImage, VlmRequest
from src.frame import Frame
from src.graph.changes import AddRelationship, AddRoadRegion
from src.graph.models import (
    InIntersection,
    InLane,
    Intersection,
    Lane,
    Provenance,
    Relationship,
    RoadRegion,
)
from src.overlay import BoxAnnotation, render_box_overlay
from src.stage import StageOutput
from src.traces import JsonValue, Trace


class RoadRegionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["Lane", "Intersection"]
    occupants: list[str] = Field(min_length=1)


class RoadLayoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    road_regions: list[RoadRegionProposal]


class RoadLayoutExtractionStage:
    """Add occupied road regions and ego-relevant traffic-flow facts."""

    name = "road-layout-extraction"
    allowed_changes = (AddRoadRegion, AddRelationship)

    def __init__(self, client: VlmClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        road_users = list(frame.graph.road_users or [])
        identity_map = render_box_overlay(
            frame.image,
            [
                BoxAnnotation(
                    bbox_xyxy=(
                        road_user.bbox.x_min,
                        road_user.bbox.y_min,
                        road_user.bbox.x_max,
                        road_user.bbox.y_max,
                    ),
                    text=road_user.id,
                    color_key=road_user.type,
                )
                for road_user in road_users
            ],
        )
        registry: list[JsonValue] = [
            {"id": "ego", "type": "EgoVehicle"},
            *(
                {"id": road_user.id, "type": road_user.type}
                for road_user in road_users
            ),
        ]
        prompt = _build_prompt(registry)
        stage_input: dict[str, JsonValue] = {
            "road_users": registry,
            "road_region_types": ["Lane", "Intersection"],
            "relationship_types": ["InLane", "InIntersection"],
        }

        response = self.client.complete(
            VlmRequest(
                prompt=prompt,
                images=(
                    VlmImage(
                        role="original",
                        data=frame.image.path.read_bytes(),
                        media_type=_image_media_type(frame.image.path.suffix),
                    ),
                    VlmImage(
                        role="identity_map",
                        data=identity_map,
                        media_type="image/png",
                    ),
                ),
                response_schema=cast(
                    dict[str, JsonValue],
                    RoadLayoutResponse.model_json_schema(),
                ),
            )
        )
        proposals = RoadLayoutResponse.model_validate(_parse_json(response.text))
        _validate_proposals(
            proposals,
            known_subjects={"ego", *(road_user.id for road_user in road_users)},
        )

        region_config: dict[
            str, tuple[type[RoadRegion], type[Relationship], str]
        ] = {
            "Lane": (Lane, InLane, "lane"),
            "Intersection": (
                Intersection,
                InIntersection,
                "intersection",
            ),
        }
        used_region_ids = {
            road_region.id for road_region in frame.graph.road_regions or []
        }
        next_region_index = {"Lane": 1, "Intersection": 1}
        changes: list[AddRoadRegion | AddRelationship] = []
        relationship_specs: list[tuple[type[Relationship], str, str]] = []
        normalized_regions: list[JsonValue] = []

        for proposal in proposals.road_regions:
            region_model, relationship_model, prefix = region_config[proposal.type]
            index = next_region_index[proposal.type]
            while f"{prefix}_{index:03d}" in used_region_ids:
                index += 1
            region_id = f"{prefix}_{index:03d}"
            next_region_index[proposal.type] = index + 1
            used_region_ids.add(region_id)

            road_region = region_model.model_validate(
                {
                    "id": region_id,
                    "provenance": [
                        Provenance(
                            source="vlm",
                            stage=self.name,
                            model=response.model,
                        )
                    ],
                }
            )
            changes.append(AddRoadRegion(road_region))
            normalized_regions.append(
                cast(
                    JsonValue,
                    road_region.model_dump(mode="json", exclude_none=True),
                )
            )
            relationship_specs.extend(
                (relationship_model, subject, region_id)
                for subject in proposal.occupants
            )

        used_relationship_ids = {
            relationship.id for relationship in frame.graph.relationships or []
        }
        relationship_index = 1
        normalized_relationships: list[JsonValue] = []
        for relationship_model, subject, object_ in relationship_specs:
            while f"relationship_{relationship_index:03d}" in used_relationship_ids:
                relationship_index += 1
            relationship_id = f"relationship_{relationship_index:03d}"
            relationship_index += 1
            used_relationship_ids.add(relationship_id)

            relationship = relationship_model.model_validate(
                {
                    "id": relationship_id,
                    "subject": subject,
                    "object": object_,
                    "provenance": [
                        Provenance(
                            source="vlm",
                            stage=self.name,
                            model=response.model,
                        )
                    ],
                }
            )
            changes.append(AddRelationship(relationship))
            normalized_relationships.append(
                cast(
                    JsonValue,
                    relationship.model_dump(mode="json", exclude_none=True),
                )
            )

        request_trace = dict(response.request or {})
        request_trace["prompt"] = "prompt.txt"
        if response.request is None:
            request_trace.update(
                {
                    "transport": "unspecified",
                    "model": response.model,
                    "images": ["original", "identity_map"],
                }
            )
        return StageOutput(
            changes=tuple(changes),
            traces=(
                Trace.text("prompt.txt", prompt),
                Trace.json("stage-input.json", stage_input),
                Trace.json("request.json", request_trace),
                Trace.bytes(
                    "identity-map.png", identity_map, media_type="image/png"
                ),
                Trace.json("response.raw.json", response.raw),
                Trace.text("response.txt", response.text),
                Trace.json("road-regions.json", normalized_regions),
                Trace.json("relationships.json", normalized_relationships),
            ),
        )


def _build_prompt(registry: list[JsonValue]) -> str:
    return f"""Identify occupied lanes and occupied intersections.

The first image is original. The second labels road users. Ego is the camera vehicle.
Use registry IDs only. Group road users that occupy the same region.
Treat all lanes equally, regardless of traffic direction. Return only clear facts.

Road-user registry:
{json.dumps(registry, separators=(",", ":"))}
"""


def _validate_proposals(
    proposals: RoadLayoutResponse,
    *,
    known_subjects: set[str],
) -> None:
    membership_keys: set[tuple[str, str]] = set()
    for region in proposals.road_regions:
        for subject in region.occupants:
            if subject not in known_subjects:
                raise ValueError(
                    f"Road-region membership has unknown subject: {subject}"
                )
            key = (subject, region.type)
            if key in membership_keys:
                raise ValueError(
                    f"Road user {subject} occupies more than one {region.type}"
                )
            membership_keys.add(key)


def _parse_json(text: str) -> JsonValue:
    stripped = text.strip()
    if not stripped:
        raise ValueError("VLM response text is empty")
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1])
    try:
        return cast(JsonValue, json.loads(stripped))
    except json.JSONDecodeError as exc:
        preview = stripped[:200].replace("\n", "\\n")
        raise ValueError(
            f"VLM response is not valid JSON: {exc}. Response starts with "
            f"{preview!r}"
        ) from exc


def _image_media_type(suffix: str) -> str:
    media_types = {
        ".gif": "image/gif",
        ".jpeg": "image/jpeg",
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    try:
        return media_types[suffix.lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported VLM image format: {suffix or '<none>'}") from exc
