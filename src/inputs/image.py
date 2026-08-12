from __future__ import annotations

from pathlib import Path

from src.frame import Frame, Image
from src.inputs.base import InputContext, SourceFrame, empty_scene
from src.traces import Trace


class ImageSource:
    """Load one front-camera frame from an image file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise ValueError(f"Image file does not exist: {self.path}")

    def load(self, context: InputContext) -> SourceFrame:
        del context  # The image is already a durable source file.
        print(f"[input:image] selected path={self.path}")
        return SourceFrame(
            frame=Frame(
                image=Image(self.path),
                graph=empty_scene(source="image", timestamp_ns=None),
            ),
            traces=(
                Trace.json(
                    "source.json",
                    {
                        "kind": "image",
                        "path": str(self.path),
                    },
                ),
            ),
        )
