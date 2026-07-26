from __future__ import annotations

from pathlib import Path
from typing import Iterator

from src.inputs.base import InputOutput


class ImageInput:
    """Seeds one graph from a front-camera image."""

    name = "input"

    def __init__(self, path: Path) -> None:
        self.path = path

    def frames(self) -> Iterator[InputOutput]:
        raise NotImplementedError
