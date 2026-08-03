from __future__ import annotations

import json
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from src.clients.vlm import VlmClient, VlmRequest
from src.frame import Frame
from src.graph._generated.catalog import ROAD_REGION_TARGETS
from src.graph._generated.models import Provenance, Relationship, RoadRegion
from src.stage import StageOutput
from src.stages.vlm_helper import (
    build_request_trace,
    build_vlm_images,
    parse_vlm_json,
    render_identity_map,
)
from src.traces import JsonValue, Trace


class RoadRegionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    occupants: list[str] = Field(min_length=1)


class RoadLayoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    road_regions: list[RoadRegionProposal]


class RoadLayoutExtractionStage:
    """Add occupied road regions and ego-relevant traffic-flow facts."""

    name = "road-layout-extraction"

    def __init__(self, client: VlmClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        road_users = list(frame.graph.road_users or [])
        identity_map = render_identity_map(frame)
        registry: list[JsonValue] = [
            {"id": "ego", "type": "EgoVehicle"},
            *(
                {"id": road_user.id, "type": road_user.type}
                for road_user in road_users
            ),
        ]
        region_vocabulary: list[JsonValue] = [
            {
                "type": target.model.__name__,
                "description": target.description,
                "membership_type": target.membership_model.__name__,
            }
            for target in ROAD_REGION_TARGETS
        ]
        target_by_name = {
            target.model.__name__: target for target in ROAD_REGION_TARGETS
        }
        prompt = _build_prompt(registry, region_vocabulary)
        stage_input: dict[str, JsonValue] = {
            "road_users": registry,
            "road_regions": region_vocabulary,
        }

        response = self.client.complete(
            VlmRequest(
                prompt=prompt,
                images=build_vlm_images(frame, identity_map),
                response_schema=_response_schema(tuple(target_by_name)),
            )
        )
        proposals = RoadLayoutResponse.model_validate(
            parse_vlm_json(response.text)
        )
        _validate_proposals(
            proposals,
            known_subjects={"ego", *(road_user.id for road_user in road_users)},
            known_region_types=set(target_by_name),
        )

        used_region_ids = {
            road_region.id for road_region in frame.graph.road_regions or []
        }
        next_region_index = {name: 1 for name in target_by_name}
        road_regions: list[RoadRegion] = []
        relationships: list[Relationship] = []
        relationship_specs: list[tuple[type[Relationship], str, str]] = []
        normalized_regions: list[JsonValue] = []

        for proposal in proposals.road_regions:
            target = target_by_name[proposal.type]
            prefix = target.id_prefix
            index = next_region_index[proposal.type]
            while f"{prefix}_{index:03d}" in used_region_ids:
                index += 1
            region_id = f"{prefix}_{index:03d}"
            next_region_index[proposal.type] = index + 1
            used_region_ids.add(region_id)

            road_region = target.model.model_validate(
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
            road_regions.append(road_region)
            normalized_regions.append(
                cast(
                    JsonValue,
                    road_region.model_dump(mode="json", exclude_none=True),
                )
            )
            relationship_specs.extend(
                (target.membership_model, subject, region_id)
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
            relationships.append(relationship)
            normalized_relationships.append(
                cast(
                    JsonValue,
                    relationship.model_dump(mode="json", exclude_none=True),
                )
            )

        request_trace = build_request_trace(response)
        return StageOutput(
            road_regions=tuple(road_regions),
            relationships=tuple(relationships),
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


def _build_prompt(
    registry: list[JsonValue], region_vocabulary: list[JsonValue]
) -> str:
    return f"""Identify occupied road regions from the schema vocabulary.

The first image is original. The second labels road users. Ego is the camera vehicle.
Use registry IDs only. Group road users that occupy the same region.
Return only clear facts.

Road-user registry:
{json.dumps(registry, separators=(",", ":"))}

Road-region vocabulary:
{json.dumps(region_vocabulary, separators=(",", ":"))}
"""


def _validate_proposals(
    proposals: RoadLayoutResponse,
    *,
    known_subjects: set[str],
    known_region_types: set[str],
) -> None:
    membership_keys: set[tuple[str, str]] = set()
    for region in proposals.road_regions:
        if region.type not in known_region_types:
            raise ValueError(f"Unknown road-region type: {region.type}")
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


def _response_schema(region_types: tuple[str, ...]) -> dict[str, JsonValue]:
    schema = RoadLayoutResponse.model_json_schema()
    proposal = cast(dict[str, Any], schema["$defs"]["RoadRegionProposal"])
    properties = cast(dict[str, Any], proposal["properties"])
    type_schema = cast(dict[str, Any], properties["type"])
    type_schema["enum"] = list(region_types)
    return cast(dict[str, JsonValue], schema)
