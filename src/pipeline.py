from __future__ import annotations

from pathlib import Path
from typing import Sequence

from src.frame import Frame
from src.graph.apply import GraphChangeApplier
from src.graph.validation import GraphValidator
from src.inputs.base import InputSource
from src.stage import Stage
from src.traces import TraceStore


class Pipeline:
    """Runs input and enrichment stages and publishes validated stage results."""

    def __init__(
        self,
        stages: Sequence[Stage],
        *,
        change_applier: GraphChangeApplier,
        graph_validator: GraphValidator,
        trace_store: TraceStore,
    ) -> None:
        self.stages = tuple(stages)
        self.change_applier = change_applier
        self.graph_validator = graph_validator
        self.trace_store = trace_store

    def run(self, source: InputSource, *, output_root: Path) -> tuple[Frame, ...]:
        """Run the source and stages, publishing ``01-input``, ``02-*``, etc."""

        raise NotImplementedError
