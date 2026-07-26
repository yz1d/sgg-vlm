from __future__ import annotations

from pathlib import Path

from src.frame import Frame, Image
from src.inputs.base import InputContext, SourceFrame, empty_scene
from src.traces import Trace


FRONT_CAMERA = "ring_front_center"


class Av2Source:
    """Load one raw front-center image from an Argoverse 2 Sensor log."""

    name = "input"

    def __init__(self, log_directory: Path, *, camera_frame_index: int = 0) -> None:
        self.log_directory = Path(log_directory)
        if camera_frame_index < 0:
            raise ValueError("AV2 camera frame index must be non-negative")
        self.camera_frame_index = camera_frame_index

    def load(self, context: InputContext) -> SourceFrame:
        del context  # AV2 images are already durable source files.
        camera_directory = (
            self.log_directory / "sensors" / "cameras" / FRONT_CAMERA
        )
        if not camera_directory.is_dir():
            raise FileNotFoundError(
                f"AV2 front-camera directory does not exist: {camera_directory}"
            )

        try:
            images = sorted(camera_directory.glob("*.jpg"), key=_image_timestamp)
        except ValueError as exc:
            raise ValueError(
                f"AV2 camera image does not have a timestamp filename: {exc}"
            ) from exc
        if not images:
            raise FileNotFoundError(
                f"No AV2 front-camera images found: {camera_directory}"
            )
        if self.camera_frame_index >= len(images):
            raise IndexError(
                f"AV2 camera frame index {self.camera_frame_index} is outside "
                f"the {len(images)} available frames"
            )

        image_path = images[self.camera_frame_index]
        timestamp_ns = _image_timestamp(image_path)
        split = self.log_directory.parent.name
        log_id = self.log_directory.name
        print(
            f"[input:av2] selected log={log_id} "
            f"frame={self.camera_frame_index} timestamp_ns={timestamp_ns}"
        )
        return SourceFrame(
            frame=Frame(
                image=Image(image_path),
                graph=empty_scene(source="av2", timestamp_ns=timestamp_ns),
            ),
            traces=(
                Trace.json(
                    "source.json",
                    {
                        "kind": "av2_sensor",
                        "dataset_root": str(self.log_directory.parent.parent),
                        "split": split,
                        "log_id": log_id,
                        "camera": FRONT_CAMERA,
                        "camera_frame_index": self.camera_frame_index,
                        "camera_timestamp_ns": timestamp_ns,
                        "source_image_path": str(image_path),
                    },
                ),
            ),
        )


def _image_timestamp(path: Path) -> int:
    return int(path.stem)
