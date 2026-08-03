from __future__ import annotations

import json
from typing import cast

from src.clients.vlm import VlmImage, VlmResponse
from src.frame import Frame
from src.overlay import BoxAnnotation, render_box_overlay
from src.traces import JsonValue


def render_identity_map(frame: Frame) -> bytes:
    """Render stable road-user identifiers over the primary image."""

    return render_box_overlay(
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
            for road_user in frame.graph.road_users or []
        ],
    )


def build_original_vlm_image(frame: Frame) -> VlmImage:
    """Build the original image for a VLM request."""

    return VlmImage(
        role="original",
        data=frame.image.path.read_bytes(),
        media_type=_image_media_type(frame.image.path.suffix),
    )


def build_vlm_images(frame: Frame, identity_map: bytes) -> tuple[VlmImage, ...]:
    """Build the original and identity-map images shared by VLM stages."""

    return (
        build_original_vlm_image(frame),
        VlmImage(
            role="identity_map",
            data=identity_map,
            media_type="image/png",
        ),
    )


def parse_vlm_json(text: str) -> JsonValue:
    """Parse a VLM JSON response with a useful error preview."""

    stripped = text.strip()
    if not stripped:
        raise ValueError("VLM response text is empty")
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1])
    try:
        return cast(JsonValue, json.loads(stripped))
    except json.JSONDecodeError as exc:
        preview = stripped[:200].replace("\n", "\\n")
        raise ValueError(
            f"VLM response is not valid JSON: {exc}. Response starts with "
            f"{preview!r}"
        ) from exc


def build_request_trace(
    response: VlmResponse,
    *,
    image_roles: tuple[str, ...] = ("original", "identity_map"),
) -> dict[str, JsonValue]:
    """Build the shared request manifest for a completed VLM call."""

    trace = dict(response.request or {})
    trace["prompt"] = "prompt.txt"
    if response.request is None:
        trace.update(
            {
                "transport": "unspecified",
                "model": response.model,
                "images": list(image_roles),
            }
        )
    return trace


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
