from __future__ import annotations

from src.clients.object_detection import ObjectDetectionClient
from src.frame import Frame
from src.graph.changes import AddRoadUser
from src.graph.detection import detection_targets
from src.graph.models import (
    BoundingBox2D,
    RoadUserDecision,
    RoadUserProvenance,
)
from src.overlay import BoxAnnotation, render_box_overlay
from src.stage import StageOutput
from src.traces import JsonValue, Trace


class ObjectDetectionStage:
    """Add road users detected from the frame's primary image."""

    name = "object-detection"
    allowed_changes = (AddRoadUser,)

    def __init__(self, client: ObjectDetectionClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        targets = detection_targets()
        if not targets:
            raise ValueError("The graph schema defines no object-detection prompts")
        prompts = tuple(target.prompt for target in targets)
        target_by_prompt = {target.prompt.casefold(): target for target in targets}
        batch = self.client.detect(frame.image, prompts)

        used_ids = {road_user.id for road_user in frame.graph.road_users or []}
        next_id = 1
        changes: list[AddRoadUser] = []
        annotations: list[BoxAnnotation] = []
        normalized: list[JsonValue] = []
        for detection in batch.detections:
            target = target_by_prompt.get(detection.label.casefold())
            if target is None:
                raise ValueError(
                    f"Object-detection client returned an unrequested label: "
                    f"{detection.label!r}"
                )
            while f"road_user_{next_id:03d}" in used_ids:
                next_id += 1
            road_user_id = f"road_user_{next_id:03d}"
            used_ids.add(road_user_id)
            next_id += 1

            provenance = RoadUserProvenance(
                source="object-detection",
                stage=self.name,
                model=batch.model,
                source_confidence=detection.confidence,
                supports=[
                    RoadUserDecision.existence,
                    RoadUserDecision.classification,
                    RoadUserDecision.bounding_box,
                ],
            )
            road_user = target.road_user_model.model_validate(
                {
                    "id": road_user_id,
                    "bbox": BoundingBox2D(
                        x_min=detection.bbox_xyxy[0],
                        y_min=detection.bbox_xyxy[1],
                        x_max=detection.bbox_xyxy[2],
                        y_max=detection.bbox_xyxy[3],
                    ),
                    "states": [],
                    "provenance": [provenance],
                }
            )
            changes.append(AddRoadUser(road_user))
            annotations.append(
                BoxAnnotation(
                    bbox_xyxy=detection.bbox_xyxy,
                    text=(
                        f"{road_user_id} {road_user.type} "
                        f"{detection.confidence:.2f}"
                    ),
                    color_key=road_user.type,
                )
            )
            normalized.append(
                {
                    "road_user_id": road_user_id,
                    "type": road_user.type,
                    "label": detection.label,
                    "bbox_xyxy": list(detection.bbox_xyxy),
                    "confidence": detection.confidence,
                }
            )

        request: dict[str, JsonValue] = {
            "image": frame.image.path.name,
            "model": batch.model,
            "prompts": list(prompts),
        }
        return StageOutput(
            changes=tuple(changes),
            traces=(
                Trace.json("request.json", request),
                Trace.json("response.raw.json", batch.raw_response),
                Trace.json("detections.json", normalized),
                Trace.bytes(
                    "overlay.png",
                    render_box_overlay(frame.image, annotations),
                    media_type="image/png",
                ),
            ),
        )
