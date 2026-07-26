from __future__ import annotations

from typing import Protocol, Sequence

from src.graph.changes import SceneChange
from src.graph.models import Scene


class GraphChangeError(ValueError):
    """A requested semantic change violates graph-domain rules."""


class GraphChangeApplier(Protocol):
    """Applies semantic changes atomically to a graph copy."""

    def apply(self, graph: Scene, changes: Sequence[SceneChange]) -> Scene: ...
