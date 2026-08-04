from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from src.frame import Image
from src.traces import JsonValue


@dataclass(frozen=True, slots=True)
class Detection:
    """One provider-normalized object detection in pixel XYXY coordinates."""

    label: str
    bbox_xyxy: tuple[float, float, float, float]
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class DetectionBatch:
    """Normalized detections and the provider response that produced them."""

    model: str
    detections: tuple[Detection, ...]
    raw_response: JsonValue
    request: dict[str, JsonValue] | None = None


class ObjectDetectionClient(Protocol):
    """Common interface implemented by object-detection providers."""

    def detect(self, image: Image, labels: Sequence[str]) -> DetectionBatch: ...
