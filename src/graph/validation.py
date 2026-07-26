from __future__ import annotations

from typing import Protocol

from src.graph.models import Scene


class GraphValidationError(ValueError):
    """A complete graph violates its structural or semantic contract."""


class GraphValidator(Protocol):
    def validate(self, graph: Scene) -> None: ...
