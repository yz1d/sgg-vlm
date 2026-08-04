from __future__ import annotations

import math

from PIL import Image as PillowImage

from src.clients.object_detection import ObjectDetectionClient
from src.frame import Frame
from src.graph._generated.catalog import DETECTION_TARGETS
from src.graph._generated.models import (
    BoundingBox2D,
    PerceivedRoadUser,
    RoadUserDecision,
    RoadUserProvenance,
)
from src.overlay import BoxAnnotation, render_box_overlay
from src.stage import StageOutput
from src.traces import JsonValue, Trace


class ObjectDetectionStage:
    """Add road users detected from the frame's primary image."""

    name = "object-detection"

    def __init__(self, client: ObjectDetectionClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        targets = DETECTION_TARGETS
        if not targets:
            raise ValueError("The graph schema defines no object-detection prompts")
        prompts = tuple(target.prompt for target in targets)
        target_by_prompt = {target.prompt.casefold(): target for target in targets}
        batch = self.client.detect(frame.image, prompts)
        with PillowImage.open(frame.image.path) as image:
            image_width, image_height = image.size

        used_ids = {road_user.id for road_user in frame.graph.road_users or []}
        next_id = 1
        road_users: list[PerceivedRoadUser] = []
        annotations: list[BoxAnnotation] = []
        normalized: list[JsonValue] = []
        clipped_count = 0
        discarded_count = 0
        for detection in batch.detections:
            target = target_by_prompt.get(detection.label.casefold())
            if target is None:
                raise ValueError(
                    f"Object-detection client returned an unrequested label: "
                    f"{detection.label!r}"
                )
            bbox = _clip_bbox(
                detection.bbox_xyxy,
                width=image_width,
                height=image_height,
            )
            if bbox is None:
                discarded_count += 1
                continue
            if bbox != detection.bbox_xyxy:
                clipped_count += 1

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
            road_user = target.model.model_validate(
                {
                    "id": road_user_id,
                    "bbox": BoundingBox2D(
                        x_min=bbox[0],
                        y_min=bbox[1],
                        x_max=bbox[2],
                        y_max=bbox[3],
                    ),
                    "provenance": [provenance],
                }
            )
            road_users.append(road_user)
            annotations.append(
                BoxAnnotation(
                    bbox_xyxy=bbox,
                    text=(
                        f"{road_user_id} {road_user.type}"
                        + (
                            f" {detection.confidence:.2f}"
                            if detection.confidence is not None
                            else ""
                        )
                    ),
                    color_key=road_user.type,
                )
            )
            normalized.append(
                {
                    "road_user_id": road_user_id,
                    "type": road_user.type,
                    "label": detection.label,
                    "bbox_xyxy": list(bbox),
                    **(
                        {"confidence": detection.confidence}
                        if detection.confidence is not None
                        else {}
                    ),
                }
            )

        if clipped_count or discarded_count:
            print(
                f"[object-detection] normalized boxes clipped={clipped_count} "
                f"discarded={discarded_count} "
                f"image={image_width}x{image_height}"
            )

        request: dict[str, JsonValue] = dict(batch.request or {})
        request.update(
            {
                "image": frame.image.path.name,
                "model": batch.model,
                "prompts": list(prompts),
            }
        )
        return StageOutput(
            road_users=tuple(road_users),
            traces=(
                Trace.json("request.json", request),
                Trace.json("response.raw.json", batch.raw_response),
                Trace.json("detections.json", normalized),
                Trace.bytes(
                    "overlay.png",
                    render_box_overlay(frame.image, annotations),
                ),
            ),
        )


def _clip_bbox(
    bbox: tuple[float, float, float, float],
    *,
    width: int,
    height: int,
) -> tuple[float, float, float, float] | None:
    if not all(math.isfinite(coordinate) for coordinate in bbox):
        return None
    x_min = max(0.0, min(float(width), bbox[0]))
    y_min = max(0.0, min(float(height), bbox[1]))
    x_max = max(0.0, min(float(width), bbox[2]))
    y_max = max(0.0, min(float(height), bbox[3]))
    if x_min >= x_max or y_min >= y_max:
        return None
    return x_min, y_min, x_max, y_max
