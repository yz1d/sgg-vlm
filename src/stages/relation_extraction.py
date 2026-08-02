from __future__ import annotations

from collections.abc import Mapping
import json
from typing import cast

from pydantic import BaseModel, ConfigDict

from src.clients.vlm import VlmClient, VlmImage, VlmRequest
from src.frame import Frame
from src.graph.changes import AddObjectState, AddRelationship
from src.graph.extraction import (
    RelationshipTarget,
    StateTarget,
    relationship_targets,
    state_targets,
)
from src.graph.models import Provenance
from src.overlay import BoxAnnotation, render_box_overlay
from src.stage import StageOutput
from src.traces import JsonValue, Trace


class RelationshipProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    type: str


class ObjectStateProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    type: str
    attributes: dict[str, str]


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationships: list[RelationshipProposal]
    states: list[ObjectStateProposal]


class RelationExtractionStage:
    """Add schema-defined object-to-ego relationships and object states."""

    name = "relation-extraction"
    allowed_changes = (AddRelationship, AddObjectState)

    def __init__(self, client: VlmClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        road_users = list(frame.graph.road_users or [])
        relationship_vocabulary = relationship_targets()
        state_vocabulary = state_targets()
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
            {"id": road_user.id, "type": road_user.type}
            for road_user in road_users
        ]
        vocabulary = _vocabulary_payload(
            relationship_vocabulary, state_vocabulary
        )
        prompt = _build_prompt(registry, vocabulary)
        stage_input: dict[str, JsonValue] = {
            "road_users": registry,
            "vocabulary": vocabulary,
        }

        if not road_users:
            return StageOutput(
                traces=(
                    Trace.text("prompt.txt", prompt),
                    Trace.json("stage-input.json", stage_input),
                    Trace.json("request.json", {"skipped": "no road users"}),
                    Trace.bytes(
                        "identity-map.png", identity_map, media_type="image/png"
                    ),
                    Trace.json("relationships.json", []),
                    Trace.json("states.json", []),
                )
            )

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
                    ExtractionResponse.model_json_schema(),
                ),
            )
        )
        proposals = ExtractionResponse.model_validate(_parse_json(response.text))
        road_user_by_id = {road_user.id: road_user for road_user in road_users}
        relationship_by_name = {
            target.model.__name__: target for target in relationship_vocabulary
        }
        state_by_name = {
            target.model.__name__: target for target in state_vocabulary
        }
        _validate_proposals(
            proposals,
            road_user_by_id=road_user_by_id,
            relationship_by_name=relationship_by_name,
            state_by_name=state_by_name,
        )

        used_relationship_ids = {
            relationship.id for relationship in frame.graph.relationships or []
        }
        relationship_index = 1
        changes: list[AddRelationship | AddObjectState] = []
        normalized_relationships: list[JsonValue] = []
        for proposal in proposals.relationships:
            while f"relationship_{relationship_index:03d}" in used_relationship_ids:
                relationship_index += 1
            relationship_id = f"relationship_{relationship_index:03d}"
            used_relationship_ids.add(relationship_id)
            relationship_index += 1
            target = relationship_by_name[proposal.type]
            relationship = target.model.model_validate(
                {
                    "id": relationship_id,
                    "subject": proposal.subject,
                    "object": "ego",
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

        normalized_states: list[JsonValue] = []
        for proposal in proposals.states:
            target = state_by_name[proposal.type]
            state = target.model.model_validate(
                {
                    "subject": proposal.subject,
                    "provenance": [
                        Provenance(
                            source="vlm",
                            stage=self.name,
                            model=response.model,
                        )
                    ],
                    **proposal.attributes,
                }
            )
            changes.append(AddObjectState(state))
            normalized_states.append(
                cast(JsonValue, state.model_dump(mode="json", exclude_none=True))
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
                Trace.json("relationships.json", normalized_relationships),
                Trace.json("states.json", normalized_states),
            ),
        )


def _vocabulary_payload(
    relationships: tuple[RelationshipTarget, ...],
    states: tuple[StateTarget, ...],
) -> dict[str, JsonValue]:
    return {
        "relationships": [
            {
                "type": target.model.__name__,
                "exclusive_group": target.exclusive_group,
            }
            for target in relationships
        ],
        "states": [
            {
                "type": target.model.__name__,
                "subject_type": target.subject_model.__name__,
                "attributes": {
                    attribute.name: [value.value for value in attribute.values]
                    for attribute in target.attributes
                },
            }
            for target in states
        ],
    }


def _build_prompt(
    registry: list[JsonValue], vocabulary: dict[str, JsonValue]
) -> str:
    return f"""Extract clear schema-defined facts for these road users.

The first image is original. The second labels road users. Ego is the camera vehicle.
Every relationship describes one road user relative to ego.
Use only the registry and vocabulary. Return only clear facts.

Road-user registry:
{json.dumps(registry, separators=(",", ":"))}

Schema vocabulary:
{json.dumps(vocabulary, separators=(",", ":"))}
"""


def _validate_proposals(
    proposals: ExtractionResponse,
    *,
    road_user_by_id: Mapping[str, object],
    relationship_by_name: dict[str, RelationshipTarget],
    state_by_name: dict[str, StateTarget],
) -> None:
    relationship_keys: set[tuple[str, str]] = set()
    groups: set[tuple[str, str]] = set()
    for proposal in proposals.relationships:
        if proposal.subject not in road_user_by_id:
            raise ValueError(
                f"Relationship has unknown subject: {proposal.subject}"
            )
        target = relationship_by_name.get(proposal.type)
        if target is None:
            raise ValueError(f"Unknown relationship type: {proposal.type}")
        key = (proposal.subject, proposal.type)
        if key in relationship_keys:
            raise ValueError(f"Duplicate relationship proposal: {key}")
        relationship_keys.add(key)
        if target.exclusive_group is not None:
            group_key = (proposal.subject, target.exclusive_group)
            if group_key in groups:
                raise ValueError(
                    f"Conflicting {target.exclusive_group} relationships for "
                    f"{proposal.subject}"
                )
            groups.add(group_key)

    state_keys: set[tuple[str, str]] = set()
    for proposal in proposals.states:
        road_user = road_user_by_id.get(proposal.subject)
        if road_user is None:
            raise ValueError(f"Object state has unknown subject: {proposal.subject}")
        target = state_by_name.get(proposal.type)
        if target is None:
            raise ValueError(f"Unknown object-state type: {proposal.type}")
        if not isinstance(road_user, target.subject_model):
            raise ValueError(
                f"Object state {proposal.type} does not apply to "
                f"{getattr(road_user, 'type', type(road_user).__name__)}"
            )
        key = (proposal.subject, proposal.type)
        if key in state_keys:
            raise ValueError(f"Duplicate object-state proposal: {key}")
        state_keys.add(key)
        expected_attributes = {
            attribute.name: {value.value for value in attribute.values}
            for attribute in target.attributes
        }
        if set(proposal.attributes) != set(expected_attributes):
            raise ValueError(
                f"Object state {proposal.type} requires attributes "
                f"{sorted(expected_attributes)}"
            )
        for name, value in proposal.attributes.items():
            if not isinstance(value, str) or value not in expected_attributes[name]:
                raise ValueError(
                    f"Invalid value for {proposal.type}.{name}: {value!r}"
                )


def _parse_json(text: str) -> JsonValue:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1])
    try:
        return cast(JsonValue, json.loads(stripped))
    except json.JSONDecodeError as exc:
        raise ValueError(f"VLM response is not valid JSON: {exc}") from exc


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
