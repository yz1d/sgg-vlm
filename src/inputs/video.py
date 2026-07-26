from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

import av
from av.error import FFmpegError

from src.frame import Frame, Image
from src.inputs.base import InputContext, SourceFrame, empty_scene
from src.traces import JsonValue, Trace


class VideoSource:
    """Load one front-camera frame from a video presentation timestamp."""

    name = "input"

    def __init__(self, path: Path, *, timestamp_seconds: float = 0.0) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise ValueError(f"Video file does not exist: {self.path}")
        if timestamp_seconds < 0:
            raise ValueError("Video timestamp must be non-negative")
        self.timestamp_seconds = float(timestamp_seconds)

    def load(self, context: InputContext) -> SourceFrame:
        target = Fraction(str(self.timestamp_seconds))
        try:
            with av.open(str(self.path)) as container:
                if not container.streams.video:
                    raise ValueError(f"Video has no video stream: {self.path}")
                stream = container.streams.video[0]
                average_rate = _positive_fraction(stream.average_rate)
                for presentation_index, decoded in enumerate(container.decode(stream)):
                    timestamp, method, time_base = _frame_timestamp(
                        decoded,
                        presentation_index,
                        stream.time_base,
                        average_rate,
                    )
                    if timestamp < target:
                        continue

                    context.workspace.mkdir(parents=True, exist_ok=True)
                    image_path = context.workspace / "image.png"
                    decoded.to_image().convert("RGB").save(image_path, format="PNG")
                    timestamp_ns = round(float(timestamp) * 1_000_000_000)
                    print(
                        f"[input:video] selected frame={presentation_index} "
                        f"timestamp={float(timestamp):g}s"
                    )
                    source_trace: dict[str, JsonValue] = {
                        "kind": "video",
                        "path": str(self.path),
                        "stream_index": int(stream.index),
                        "presentation_index": presentation_index,
                        "pts": decoded.pts,
                        "time_base": _fraction_json(time_base),
                        "timestamp_method": method,
                        "timestamp_ns": timestamp_ns,
                        "requested_timestamp_seconds": self.timestamp_seconds,
                        "average_rate": _fraction_json(average_rate),
                        "display_rotation_degrees": _display_rotation(
                            decoded, stream
                        ),
                        "display_rotation_applied": False,
                    }
                    return SourceFrame(
                        frame=Frame(
                            image=Image(image_path),
                            graph=empty_scene(
                                source="video", timestamp_ns=timestamp_ns
                            ),
                        ),
                        traces=(Trace.json("source.json", source_trace),),
                    )
        except FFmpegError as exc:
            raise ValueError(f"Could not decode video {self.path}: {exc}") from exc

        raise ValueError(
            f"Video has no frame at or after {self.timestamp_seconds:g}s: {self.path}"
        )


def _frame_timestamp(
    frame: Any,
    presentation_index: int,
    stream_time_base: Any,
    average_rate: Fraction | None,
) -> tuple[Fraction, str, Fraction | None]:
    time_base = _positive_fraction(frame.time_base) or _positive_fraction(
        stream_time_base
    )
    if frame.pts is not None and time_base is not None:
        return Fraction(int(frame.pts), 1) * time_base, "pts", time_base
    if average_rate is None:
        raise ValueError(
            "Video frame has no presentation timestamp or usable average frame rate"
        )
    return Fraction(presentation_index, 1) / average_rate, "average_rate", None


def _positive_fraction(value: Any) -> Fraction | None:
    if value is None:
        return None
    try:
        result = Fraction(int(value.numerator), int(value.denominator))
    except AttributeError:
        result = Fraction(str(value))
    return result if result > 0 else None


def _fraction_json(value: Fraction | None) -> dict[str, JsonValue] | None:
    if value is None:
        return None
    return {"numerator": value.numerator, "denominator": value.denominator}


def _display_rotation(frame: Any, stream: Any) -> float | None:
    rotation = getattr(frame, "rotation", None)
    if isinstance(rotation, int | float):
        return float(rotation)
    metadata_rotation = stream.metadata.get("rotate")
    if metadata_rotation is None:
        return None
    try:
        return float(metadata_rotation)
    except ValueError:
        return None
