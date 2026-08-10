from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from src.clients.vlm import VlmClient, VlmRequest
from src.frame import Frame
from src.graph._generated.catalog import RELATION_TARGETS
from src.graph._generated.models import (
    EgoVehicle,
    Provenance,
    Relation,
    SceneObject,
    SpatialRelation,
)
from src.graph.ontology import RelationTarget
from src.stage import StageOutput
from src.stages.vlm_helper import (
    build_request_trace,
    build_vlm_images,
    parse_vlm_json,
    render_identity_map,
)
from src.traces import JsonValue, Trace


class RelationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    type: str


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relations: list[RelationProposal]


class RelationExtractionStage:
    """Add object-to-ego relations."""

    name = "relation-extraction"

    def __init__(self, client: VlmClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        objects = [
            object_
            for object_ in frame.graph.objects
            if object_.id != "ego" and object_.bbox is not None
        ]
        ego = next(
            (
                object_
                for object_ in frame.graph.objects
                if isinstance(object_, EgoVehicle) and object_.id == "ego"
            ),
            None,
        )
        if ego is None:
            raise ValueError("Scene has no ego object")
        relation_vocabulary = tuple(
            target
            for target in RELATION_TARGETS
            if issubclass(target.model, SpatialRelation)
        )
        identity_map = render_identity_map(frame)
        registry: list[JsonValue] = [
            {"id": object_.id, "type": object_.type} for object_ in objects
        ]
        vocabulary = _vocabulary_payload(relation_vocabulary)
        prompt = _build_prompt(registry, vocabulary)
        stage_input: dict[str, JsonValue] = {
            "objects": registry,
            "vocabulary": vocabulary,
        }

        if not objects:
            return StageOutput(
                traces=(
                    Trace.text("prompt.txt", prompt),
                    Trace.json("stage-input.json", stage_input),
                    Trace.json("request.json", {"skipped": "no visible scene objects"}),
                    Trace.bytes("identity-map.png", identity_map),
                    Trace.json("relations.json", []),
                )
            )

        response = self.client.complete(
            VlmRequest(
                prompt=prompt,
                images=build_vlm_images(frame, identity_map),
                response_schema=_response_schema(
                    objects,
                    relation_vocabulary,
                ),
            )
        )
        proposals = ExtractionResponse.model_validate(
            parse_vlm_json(response.text)
        )
        object_by_id = {object_.id: object_ for object_ in objects}
        relation_by_name = {
            target.model.__name__: target for target in relation_vocabulary
        }
        _validate_proposals(
            proposals,
            object_by_id=object_by_id,
            relation_by_name=relation_by_name,
        )

        used_relation_ids = {relation.id for relation in frame.graph.relations}
        relation_index = 1
        relations: list[Relation] = []
        normalized_relations: list[JsonValue] = []
        for proposal in proposals.relations:
            while f"relation_{relation_index:03d}" in used_relation_ids:
                relation_index += 1
            relation_id = f"relation_{relation_index:03d}"
            used_relation_ids.add(relation_id)
            relation_index += 1
            target = relation_by_name[proposal.type]
            relation = target.model.model_validate(
                {
                    "id": relation_id,
                    "subject": proposal.subject,
                    "object": ego.id,
                    "provenance": [
                        Provenance(
                            source="vlm",
                            stage=self.name,
                            model=response.model,
                        )
                    ],
                }
            )
            relations.append(relation)
            normalized_relations.append(
                cast(
                    JsonValue,
                    relation.model_dump(mode="json", exclude_none=True),
                )
            )

        request_trace = build_request_trace(response)
        return StageOutput(
            relations=tuple(relations),
            traces=(
                Trace.text("prompt.txt", prompt),
                Trace.json("stage-input.json", stage_input),
                Trace.json("request.json", request_trace),
                Trace.bytes("identity-map.png", identity_map),
                Trace.json("response.raw.json", response.raw),
                Trace.text("response.txt", response.text),
                Trace.json("relations.json", normalized_relations),
            ),
        )


def _vocabulary_payload(
    relations: tuple[RelationTarget, ...],
) -> dict[str, JsonValue]:
    return {
        "relation_types": [
            {
                "type": target.model.__name__,
                "description": target.description,
                "subject_type": target.subject_model.__name__,
                "object_type": target.object_model.__name__,
            }
            for target in relations
        ],
    }


def _build_prompt(
    registry: list[JsonValue], vocabulary: dict[str, JsonValue]
) -> str:
    return f"""Determine each registry object's clear spatial relations to ego, the camera vehicle.
Use the original first image and the labeled second image. Omit uncertain relations.

Registry: {json.dumps(registry, separators=(",", ":"))}
Vocabulary: {json.dumps(vocabulary, separators=(",", ":"))}
"""


def _validate_proposals(
    proposals: ExtractionResponse,
    *,
    object_by_id: Mapping[str, SceneObject],
    relation_by_name: dict[str, RelationTarget],
) -> None:
    relation_keys: set[tuple[str, str]] = set()
    groups: set[tuple[str, str]] = set()
    for proposal in proposals.relations:
        object_ = object_by_id.get(proposal.subject)
        if object_ is None:
            raise ValueError(f"Relation has unknown subject: {proposal.subject}")
        target = relation_by_name.get(proposal.type)
        if target is None:
            raise ValueError(f"Unknown relation type: {proposal.type}")
        if not isinstance(object_, target.subject_model):
            raise ValueError(
                f"Relation {proposal.type} does not apply to {object_.type}"
            )
        key = (proposal.subject, proposal.type)
        if key in relation_keys:
            raise ValueError(f"Duplicate relation proposal: {key}")
        relation_keys.add(key)
        if target.exclusive_group is not None:
            group_key = (proposal.subject, target.exclusive_group)
            if group_key in groups:
                raise ValueError(
                    f"Conflicting {target.exclusive_group} relations for "
                    f"{proposal.subject}"
                )
            groups.add(group_key)


def _response_schema(
    objects: list[SceneObject],
    relations: tuple[RelationTarget, ...],
) -> dict[str, JsonValue]:
    relation_variants: list[dict[str, Any]] = []
    for target in relations:
        subjects = [
            object_.id
            for object_ in objects
            if isinstance(object_, target.subject_model)
        ]
        if not subjects:
            continue
        relation_variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "subject": {"type": "string", "enum": subjects},
                    "type": {
                        "type": "string",
                        "enum": [target.model.__name__],
                    },
                },
                "required": ["subject", "type"],
            }
        )

    relation_items: dict[str, Any] = (
        {"anyOf": relation_variants} if relation_variants else {}
    )
    return cast(
        dict[str, JsonValue],
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "relations": {
                    "type": "array",
                    "items": relation_items,
                    **({"maxItems": 0} if not relation_variants else {}),
                },
            },
            "required": ["relations"],
        },
    )
