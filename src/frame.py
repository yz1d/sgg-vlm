from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.graph.models import Scene


@dataclass(frozen=True, slots=True)
class Image:
    """The primary front-camera image for a frame."""

    path: Path


@dataclass(frozen=True, slots=True)
class Frame:
    """A primary image and its current normalized scene graph."""

    image: Image
    graph: Scene
