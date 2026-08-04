from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Sequence, cast

from PIL import Image as PillowImage
from pydantic import BaseModel, ConfigDict, Field

from src.clients.object_detection import Detection, DetectionBatch
from src.clients.vlm import VlmClient, VlmImage, VlmRequest
from src.frame import Image
from src.traces import JsonValue


NormalizedCoordinate = Annotated[float, Field(ge=0, le=1000)]


class DetectionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    bbox: list[NormalizedCoordinate] = Field(min_length=4, max_length=4)


class DetectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detections: list[DetectionProposal]


class VlmObjectDetectionClient:
    """Detect requested object types through a general vision-language model."""

    def __init__(self, client: VlmClient) -> None:
        self.client = client

    def detect(self, image: Image, labels: Sequence[str]) -> DetectionBatch:
        if not image.path.is_file():
            raise FileNotFoundError(f"Detection image does not exist: {image.path}")
        requested_labels = tuple(label.strip() for label in labels)
        if not requested_labels or any(not label for label in requested_labels):
            raise ValueError("Object detection requires nonempty labels")
        if len({label.casefold() for label in requested_labels}) != len(
            requested_labels
        ):
            raise ValueError("Object-detection labels must be unique")

        prompt = _build_prompt(requested_labels)
        response = self.client.complete(
            VlmRequest(
                prompt=prompt,
                images=(
                    VlmImage(
                        role="original",
                        data=image.path.read_bytes(),
                        media_type=_image_media_type(image.path),
                    ),
                ),
                response_schema=cast(
                    dict[str, JsonValue], DetectionResponse.model_json_schema()
                ),
            )
        )
        proposals = DetectionResponse.model_validate(_parse_json(response.text))
        labels_by_key = {label.casefold(): label for label in requested_labels}
        with PillowImage.open(image.path) as source_image:
            image_width, image_height = source_image.size
        detections: list[Detection] = []
        for proposal in proposals.detections:
            label = labels_by_key.get(proposal.label.strip().casefold())
            if label is None:
                raise ValueError(
                    f"VLM detector returned an unrequested label: {proposal.label!r}"
                )
            x_min, y_min, x_max, y_max = proposal.bbox
            if x_min >= x_max or y_min >= y_max:
                raise ValueError(
                    f"VLM detector returned an invalid box: {proposal.bbox}"
                )
            detections.append(
                Detection(
                    label=label,
                    bbox_xyxy=(
                        x_min * image_width / 1000,
                        y_min * image_height / 1000,
                        x_max * image_width / 1000,
                        y_max * image_height / 1000,
                    ),
                )
            )

        raw = response.raw
        if raw is None:
            raw = cast(JsonValue, proposals.model_dump(mode="json"))
        request = dict(response.request or {})
        request.update(
            {
                "coordinate_space": "normalized_0_1000",
                "image": image.path.name,
                "labels": list(requested_labels),
                "prompt": prompt,
            }
        )
        return DetectionBatch(
            model=response.model,
            detections=tuple(detections),
            raw_response=raw,
            request=request,
        )


def _build_prompt(labels: tuple[str, ...]) -> str:
    label_json = json.dumps(labels, separators=(",", ":"))
    return f"""Inspect this front-camera road image and locate every visible road user.

Use exactly this label vocabulary: {label_json}
Include small or partly occluded objects when they are visible.
Classify each physical object once. Use school bus instead of bus when applicable.
Use a tight box around the visible extent. Do not infer objects outside the image.
Return JSON as detections with one label and bbox per object.
Coordinates use [x_min,y_min,x_max,y_max], normalized from 0 through 1000.
The top-left image corner is [0,0]. The bottom-right corner is [1000,1000].
"""


def _parse_json(text: str) -> JsonValue:
    try:
        return cast(JsonValue, json.loads(text))
    except json.JSONDecodeError as exc:
        preview = text[:200].replace("\n", "\\n")
        raise ValueError(
            f"VLM detection response is not valid JSON: {exc}. "
            f"Response starts with {preview!r}"
        ) from exc


def _image_media_type(path: Path) -> str:
    media_types = {
        ".jpeg": "image/jpeg",
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    try:
        return media_types[path.suffix.casefold()]
    except KeyError as exc:
        raise ValueError(
            f"VLM object detection requires a JPEG, PNG, or WebP image: {path}"
        ) from exc
