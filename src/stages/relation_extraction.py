from __future__ import annotations

from collections.abc import Mapping
import json
from typing import cast

from pydantic import BaseModel, ConfigDict

from src.clients.vlm import VlmClient, VlmRequest
from src.frame import Frame
from src.graph._generated.catalog import RELATIONSHIP_TARGETS, STATE_TARGETS
from src.graph._generated.models import ObjectState, Provenance, Relationship
from src.graph.ontology import RelationshipTarget, StateTarget
from src.stage import StageOutput
from src.stages.vlm_helper import (
    build_request_trace,
    build_vlm_images,
    parse_vlm_json,
    render_identity_map,
)
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
    """Add schema-defined entity-to-ego relationships and object states."""

    name = "relation-extraction"

    def __init__(self, client: VlmClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        perceived_entities = list(frame.graph.perceived_entities or [])
        relationship_vocabulary = tuple(
            target for target in RELATIONSHIP_TARGETS if target.extraction_enabled
        )
        state_vocabulary = STATE_TARGETS
        identity_map = render_identity_map(frame)
        registry: list[JsonValue] = [
            {"id": entity.id, "type": entity.type}
            for entity in perceived_entities
        ]
        vocabulary = _vocabulary_payload(
            relationship_vocabulary, state_vocabulary
        )
        prompt = _build_prompt(registry, vocabulary)
        stage_input: dict[str, JsonValue] = {
            "perceived_entities": registry,
            "vocabulary": vocabulary,
        }

        if not perceived_entities:
            return StageOutput(
                traces=(
                    Trace.text("prompt.txt", prompt),
                    Trace.json("stage-input.json", stage_input),
                    Trace.json(
                        "request.json",
                        {"skipped": "no perceived road entities"},
                    ),
                    Trace.bytes("identity-map.png", identity_map),
                    Trace.json("relationships.json", []),
                    Trace.json("states.json", []),
                )
            )

        response = self.client.complete(
            VlmRequest(
                prompt=prompt,
                images=build_vlm_images(frame, identity_map),
                response_schema=cast(
                    dict[str, JsonValue],
                    ExtractionResponse.model_json_schema(),
                ),
            )
        )
        proposals = ExtractionResponse.model_validate(
            parse_vlm_json(response.text)
        )
        entity_by_id = {
            entity.id: entity for entity in perceived_entities
        }
        relationship_by_name = {
            target.model.__name__: target for target in relationship_vocabulary
        }
        state_by_name = {
            target.model.__name__: target for target in state_vocabulary
        }
        _validate_proposals(
            proposals,
            entity_by_id=entity_by_id,
            relationship_by_name=relationship_by_name,
            state_by_name=state_by_name,
        )

        used_relationship_ids = {
            relationship.id for relationship in frame.graph.relationships or []
        }
        relationship_index = 1
        relationships: list[Relationship] = []
        states: list[ObjectState] = []
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
            relationships.append(relationship)
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
            states.append(state)
            normalized_states.append(
                cast(JsonValue, state.model_dump(mode="json", exclude_none=True))
            )

        request_trace = build_request_trace(response)
        return StageOutput(
            relationships=tuple(relationships),
            states=tuple(states),
            traces=(
                Trace.text("prompt.txt", prompt),
                Trace.json("stage-input.json", stage_input),
                Trace.json("request.json", request_trace),
                Trace.bytes("identity-map.png", identity_map),
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
                "description": target.description,
                "exclusive_group": target.exclusive_group,
            }
            for target in relationships
        ],
        "states": [
            {
                "type": target.model.__name__,
                "description": target.description,
                "subject_type": target.subject_model.__name__,
                "attributes": {
                    attribute.name: {
                        "description": attribute.description,
                        "values": [
                            {
                                "value": value.value,
                                "description": value.description,
                                "visual_prompt": value.prompt,
                            }
                            for value in attribute.values
                        ],
                    }
                    for attribute in target.attributes
                },
            }
            for target in states
        ],
    }


def _build_prompt(
    registry: list[JsonValue], vocabulary: dict[str, JsonValue]
) -> str:
    return f"""Extract clear schema-defined facts for these perceived road entities.

The first image is original. The second labels perceived road entities. Ego is the camera vehicle.
Every relationship describes one perceived road entity relative to ego.
Object states apply only to compatible road-user types in the vocabulary.
Use only the registry and vocabulary. Return only clear facts.

Perceived-entity registry:
{json.dumps(registry, separators=(",", ":"))}

Schema vocabulary:
{json.dumps(vocabulary, separators=(",", ":"))}
"""


def _validate_proposals(
    proposals: ExtractionResponse,
    *,
    entity_by_id: Mapping[str, object],
    relationship_by_name: dict[str, RelationshipTarget],
    state_by_name: dict[str, StateTarget],
) -> None:
    relationship_keys: set[tuple[str, str]] = set()
    groups: set[tuple[str, str]] = set()
    for proposal in proposals.relationships:
        if proposal.subject not in entity_by_id:
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
        entity = entity_by_id.get(proposal.subject)
        if entity is None:
            raise ValueError(f"Object state has unknown subject: {proposal.subject}")
        target = state_by_name.get(proposal.type)
        if target is None:
            raise ValueError(f"Unknown object-state type: {proposal.type}")
        if not isinstance(entity, target.subject_model):
            raise ValueError(
                f"Object state {proposal.type} does not apply to "
                f"{getattr(entity, 'type', type(entity).__name__)}"
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
