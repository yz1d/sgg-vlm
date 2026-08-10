from __future__ import annotations

import json
from typing import Annotated, Any, cast

from PIL import Image as PillowImage
from pydantic import BaseModel, ConfigDict, Field

from src.clients.vlm import VlmClient, VlmRequest
from src.frame import Frame
from src.graph._generated.catalog import OBJECT_TARGETS
from src.graph._generated.models import (
    BoundingBox2D,
    ObjectDecision,
    ObjectProvenance,
    SceneObject,
)
from src.graph.ontology import ObjectTarget
from src.overlay import BoxAnnotation, render_box_overlay
from src.stage import StageOutput
from src.stages.vlm_helper import (
    build_original_vlm_image,
    build_request_trace,
    parse_vlm_json,
)
from src.traces import JsonValue, Trace

NormalizedCoordinate = Annotated[float, Field(ge=0, le=1000)]


class DetectionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    bbox: list[NormalizedCoordinate] = Field(min_length=4, max_length=4)
    attributes: dict[str, str]


class DetectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detections: list[DetectionProposal]


class ObjectDetectionStage:
    """Add scene objects detected from the frame's primary image."""

    name = "object-detection"

    def __init__(
        self,
        client: VlmClient,
        *,
        min_object_area_ratio: float = 0.0,
    ) -> None:
        if not 0 <= min_object_area_ratio <= 1:
            raise ValueError("min_object_area_ratio must be between 0 and 1")
        self.client = client
        self.min_object_area_ratio = min_object_area_ratio

    def run(self, frame: Frame) -> StageOutput:
        targets = tuple(
            target
            for target in OBJECT_TARGETS
            if target.model.model_fields["bbox"].is_required()
        )
        target_by_type = {target.model.__name__: target for target in targets}
        vocabulary: list[JsonValue] = [
            {
                "type": target.model.__name__,
                "description": target.description,
                "attributes": {
                    attribute.name: {
                        "description": attribute.description,
                        "required": attribute.required,
                        "values": [
                            {
                                "value": value.value,
                                "description": value.description,
                            }
                            for value in attribute.values
                        ],
                    }
                    for attribute in target.attributes
                },
            }
            for target in targets
        ]
        prompt = _build_prompt(vocabulary)
        stage_input: dict[str, JsonValue] = {
            "object_types": vocabulary,
            "coordinate_space": "normalized_0_1000",
            "min_object_area_ratio": self.min_object_area_ratio,
        }
        response = self.client.complete(
            VlmRequest(
                prompt=prompt,
                images=(build_original_vlm_image(frame),),
                response_schema=_response_schema(targets),
            )
        )
        proposals = DetectionResponse.model_validate(
            parse_vlm_json(response.text)
        )
        with PillowImage.open(frame.image.path) as image:
            image_width, image_height = image.size

        used_ids = {object_.id for object_ in frame.graph.objects}
        next_id = 1
        objects: list[SceneObject] = []
        annotations: list[BoxAnnotation] = []
        normalized: list[JsonValue] = []
        filtered: list[JsonValue] = []
        clipped_count = 0
        discarded_count = 0
        image_area = image_width * image_height
        for proposal in proposals.detections:
            target = target_by_type.get(proposal.type)
            if target is None:
                raise ValueError(
                    f"VLM detector returned an unrequested type: {proposal.type!r}"
                )
            expected_attributes = {
                attribute.name: attribute for attribute in target.attributes
            }
            required_attributes = {
                name
                for name, attribute in expected_attributes.items()
                if attribute.required
            }
            if not required_attributes.issubset(proposal.attributes):
                raise ValueError(
                    f"{proposal.type} requires attributes "
                    f"{sorted(required_attributes)}"
                )
            if not set(proposal.attributes).issubset(expected_attributes):
                raise ValueError(
                    f"{proposal.type} has unknown attributes "
                    f"{sorted(set(proposal.attributes) - set(expected_attributes))}"
                )
            for name, value in proposal.attributes.items():
                valid_values = {
                    item.value for item in expected_attributes[name].values
                }
                if value not in valid_values:
                    raise ValueError(
                        f"Invalid value for {proposal.type}.{name}: {value!r}"
                    )

            normalized_bbox = tuple(proposal.bbox)
            x_min, y_min, x_max, y_max = normalized_bbox
            if x_min >= x_max or y_min >= y_max:
                raise ValueError(
                    f"VLM detector returned an invalid box: {proposal.bbox}"
                )
            source_bbox = (
                x_min * image_width / 1000,
                y_min * image_height / 1000,
                x_max * image_width / 1000,
                y_max * image_height / 1000,
            )
            bbox = _clip_bbox(
                source_bbox,
                width=image_width,
                height=image_height,
            )
            if bbox is None:
                discarded_count += 1
                continue
            if bbox != source_bbox:
                clipped_count += 1
            area_ratio = (
                (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) / image_area
            )
            if area_ratio < self.min_object_area_ratio:
                filtered.append(
                    {
                        "type": proposal.type,
                        "bbox_xyxy": list(bbox),
                        "area_ratio": area_ratio,
                        "reason": "below_min_object_area_ratio",
                    }
                )
                continue

            while f"object_{next_id:03d}" in used_ids:
                next_id += 1
            object_id = f"object_{next_id:03d}"
            used_ids.add(object_id)
            next_id += 1

            provenance = ObjectProvenance(
                source="vlm",
                stage=self.name,
                model=response.model,
                supports=[
                    ObjectDecision.existence,
                    ObjectDecision.classification,
                    ObjectDecision.bounding_box,
                    *(
                        [ObjectDecision.attributes]
                        if proposal.attributes
                        else []
                    ),
                ],
            )
            object_ = target.model.model_validate(
                {
                    "id": object_id,
                    "bbox": BoundingBox2D(
                        x_min=bbox[0],
                        y_min=bbox[1],
                        x_max=bbox[2],
                        y_max=bbox[3],
                    ),
                    "provenance": [provenance],
                    **proposal.attributes,
                }
            )
            objects.append(object_)
            annotations.append(
                BoxAnnotation(
                    bbox_xyxy=bbox,
                    text=f"{object_id} {object_.type}",
                    color_key=object_.type,
                )
            )
            normalized.append(
                {
                    "object_id": object_id,
                    "type": object_.type,
                    "bbox_xyxy": list(bbox),
                    "attributes": proposal.attributes,
                    "area_ratio": area_ratio,
                }
            )

        if clipped_count or discarded_count or filtered:
            print(
                f"[object-detection] normalized boxes clipped={clipped_count} "
                f"discarded={discarded_count} filtered_small={len(filtered)} "
                f"min_area_ratio={self.min_object_area_ratio:g} "
                f"image={image_width}x{image_height}"
            )

        return StageOutput(
            objects=tuple(objects),
            traces=(
                Trace.text("prompt.txt", prompt),
                Trace.json("stage-input.json", stage_input),
                Trace.json(
                    "request.json",
                    build_request_trace(response, image_roles=("original",)),
                ),
                Trace.json("response.raw.json", response.raw),
                Trace.text("response.txt", response.text),
                Trace.json("detections.json", normalized),
                Trace.json("filtered-detections.json", filtered),
                Trace.bytes(
                    "overlay.png",
                    render_box_overlay(frame.image, annotations),
                ),
            ),
        )


def _build_prompt(vocabulary: list[JsonValue]) -> str:
    vocabulary_json = json.dumps(vocabulary, separators=(",", ":"))
    return f"""Inspect this front-camera road image and locate every requested scene object.

Use only object types from this schema vocabulary: {vocabulary_json}
Include small or partly occluded objects when they are visible.
Classify each physical object once. Use the most specific applicable schema type.
Use a tight box around the visible extent of the represented object or area.
Do not infer objects outside the image.
Include required attributes. Omit optional attributes when the visual state is unclear.
Return JSON as detections with one type, bbox, and attributes object per object.
Coordinates use [x_min,y_min,x_max,y_max], normalized from 0 through 1000.
The top-left image corner is [0,0]. The bottom-right corner is [1000,1000].
"""


def _response_schema(
    targets: tuple[ObjectTarget, ...],
) -> dict[str, JsonValue]:
    variants: list[dict[str, Any]] = []
    for target in targets:
        attribute_properties = {
            attribute.name: {
                "type": "string",
                "enum": [value.value for value in attribute.values],
            }
            for attribute in target.attributes
        }
        required_attributes = [
            attribute.name
            for attribute in target.attributes
            if attribute.required
        ]
        variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [target.model.__name__],
                    },
                    "bbox": {
                        "type": "array",
                        "items": {"type": "number", "minimum": 0, "maximum": 1000},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "attributes": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": attribute_properties,
                        "required": required_attributes,
                    },
                },
                "required": ["type", "bbox", "attributes"],
            }
        )
    return cast(
        dict[str, JsonValue],
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "detections": {
                    "type": "array",
                    "items": {"anyOf": variants},
                }
            },
            "required": ["detections"],
        },
    )


def _clip_bbox(
    bbox: tuple[float, float, float, float],
    *,
    width: int,
    height: int,
) -> tuple[float, float, float, float] | None:
    x_min = max(0.0, min(float(width), bbox[0]))
    y_min = max(0.0, min(float(height), bbox[1]))
    x_max = max(0.0, min(float(width), bbox[2]))
    y_max = max(0.0, min(float(height), bbox[3]))
    if x_min >= x_max or y_min >= y_max:
        return None
    return x_min, y_min, x_max, y_max
