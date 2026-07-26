from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any, Sequence, cast

import requests
from dotenv import load_dotenv

from src.clients.object_detection import (
    Detection,
    DetectionBatch,
    ObjectDetectionClient,
)
from src.frame import Image
from src.traces import JsonValue

TASK_URL = "https://api.deepdataspace.com/v2/task/grounding_dino/detection"
STATUS_URL = "https://api.deepdataspace.com/v2/task_status/{task_uuid}"
TOKEN_ENV = "DEEPDATASPACE_TOKEN"
DEFAULT_MODEL = "GroundingDino-1.6-Pro"


class GroundingDinoProClient(ObjectDetectionClient):
    """Grounding DINO 1.6 Pro through the DeepDataSpace task API."""

    def __init__(
        self,
        *,
        token: str | None = None,
        model: str = DEFAULT_MODEL,
        bbox_threshold: float = 0.25,
        iou_threshold: float = 0.8,
        poll_interval_seconds: float = 1.0,
        timeout_seconds: float = 120.0,
    ) -> None:
        load_dotenv()
        self.token = token or os.environ.get(TOKEN_ENV)
        if not self.token:
            raise ValueError(f"Set {TOKEN_ENV} in the environment or .env")
        if not model:
            raise ValueError("Grounding DINO model cannot be empty")
        if not 0 <= bbox_threshold <= 1:
            raise ValueError("Grounding DINO bbox threshold must be between 0 and 1")
        if not 0 <= iou_threshold <= 1:
            raise ValueError("Grounding DINO IoU threshold must be between 0 and 1")
        if poll_interval_seconds <= 0:
            raise ValueError("Grounding DINO poll interval must be positive")
        if timeout_seconds <= 0:
            raise ValueError("Grounding DINO timeout must be positive")
        self.model = model
        self.bbox_threshold = float(bbox_threshold)
        self.iou_threshold = float(iou_threshold)
        self.poll_interval_seconds = float(poll_interval_seconds)
        self.timeout_seconds = float(timeout_seconds)

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

        body = {
            "model": self.model,
            "image": _encode_image(image.path),
            "prompt": {
                "type": "text",
                "text": ".".join(requested_labels) + ".",
            },
            "targets": ["bbox"],
            "bbox_threshold": self.bbox_threshold,
            "iou_threshold": self.iou_threshold,
        }
        headers = {"Content-Type": "application/json", "Token": self.token}
        print(
            f"[object-detection:grounding-dino] request started: "
            f"image={image.path.name} model={self.model}"
        )
        started = time.monotonic()
        try:
            with requests.Session() as session:
                response = session.post(
                    TASK_URL,
                    json=body,
                    headers=headers,
                    timeout=(10, 60),
                )
                response.raise_for_status()
                created = _response_payload(response, "creating task")
                _require_success(created, "creating task")
                task_uuid = _task_uuid(created)
                raw = self._poll(session, task_uuid, headers)
        except requests.RequestException as exc:
            raise RuntimeError(f"Grounding DINO request failed: {exc}") from exc

        detections = _normalize(raw, requested_labels)
        print(
            f"[object-detection:grounding-dino] request finished: "
            f"task={task_uuid} detections={len(detections)} "
            f"elapsed={time.monotonic() - started:.1f}s"
        )
        return DetectionBatch(
            model=self.model,
            detections=detections,
            raw_response=cast(JsonValue, raw),
        )

    def _poll(
        self,
        session: requests.Session,
        task_uuid: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_seconds
        url = STATUS_URL.format(task_uuid=task_uuid)
        while True:
            response = session.get(url, headers=headers, timeout=(10, 60))
            response.raise_for_status()
            raw = _response_payload(response, "querying task")
            _require_success(raw, "querying task")
            data = raw.get("data")
            status = data.get("status") if isinstance(data, dict) else None
            if status == "success":
                return raw
            if status == "failed":
                raise RuntimeError(f"Grounding DINO task failed: {raw}")
            if status not in {"waiting", "running"}:
                raise RuntimeError(f"Unexpected Grounding DINO task status: {status}")
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Timed out waiting for Grounding DINO task {task_uuid}"
                )
            time.sleep(self.poll_interval_seconds)


def _encode_image(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in {".jpg", ".jpeg"}:
        media_type = "image/jpeg"
    elif suffix == ".png":
        media_type = "image/png"
    else:
        raise ValueError(f"Grounding DINO requires a JPEG or PNG image: {path}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _response_payload(response: requests.Response, operation: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except requests.JSONDecodeError as exc:
        raise RuntimeError(
            f"Grounding DINO returned invalid JSON while {operation}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"Grounding DINO returned a non-object response while {operation}"
        )
    return payload


def _require_success(payload: dict[str, Any], operation: str) -> None:
    if payload.get("code") != 0:
        raise RuntimeError(f"Grounding DINO API error while {operation}: {payload}")


def _task_uuid(payload: dict[str, Any]) -> str:
    data = payload.get("data")
    task_uuid = data.get("task_uuid") if isinstance(data, dict) else None
    if not isinstance(task_uuid, str) or not task_uuid:
        raise RuntimeError("Grounding DINO task response has no task UUID")
    return task_uuid


def _normalize(
    raw: dict[str, Any], requested_labels: tuple[str, ...]
) -> tuple[Detection, ...]:
    labels = {label.casefold(): label for label in requested_labels}
    data = raw.get("data")
    result = data.get("result") if isinstance(data, dict) else None
    objects = result.get("objects") if isinstance(result, dict) else None
    if objects is None:
        return ()
    if not isinstance(objects, list):
        raise RuntimeError("Grounding DINO result objects must be an array")

    detections: list[Detection] = []
    for item in objects:
        if not isinstance(item, dict):
            continue
        category = item.get("category")
        bbox = item.get("bbox")
        score = item.get("score")
        if (
            not isinstance(category, str)
            or category.strip().casefold() not in labels
            or not isinstance(bbox, list)
            or len(bbox) < 4
            or isinstance(score, bool)
            or not isinstance(score, int | float)
        ):
            continue
        coordinates = bbox[:4]
        if any(
            isinstance(value, bool) or not isinstance(value, int | float)
            for value in coordinates
        ):
            continue
        detections.append(
            Detection(
                label=labels[category.strip().casefold()],
                bbox_xyxy=cast(
                    tuple[float, float, float, float],
                    tuple(float(value) for value in coordinates),
                ),
                confidence=float(score),
            )
        )
    return tuple(detections)
