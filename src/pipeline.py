from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Sequence

from src.frame import Frame, Image
from src.graph.apply import DefaultGraphChangeApplier, GraphChangeApplier
from src.graph._generated.models import Scene
from src.graph.render import render_graphviz
from src.graph.validation import validate_scene
from src.inputs.base import InputContext, InputSource
from src.stage import Stage
from src.traces import FileTraceStore, Trace, TraceStore


class Pipeline:
    """Run one input frame through ordered graph enrichment stages."""

    def __init__(
        self,
        stages: Sequence[Stage] = (),
        *,
        change_applier: GraphChangeApplier | None = None,
        trace_store: TraceStore | None = None,
    ) -> None:
        self.stages = tuple(stages)
        self.change_applier = change_applier or DefaultGraphChangeApplier()
        self.trace_store = trace_store or FileTraceStore()
        for stage in self.stages:
            if not re.fullmatch(r"[a-z][a-z0-9-]*", stage.name):
                raise ValueError(f"Invalid stage name: {stage.name}")

    def run(self, source: InputSource, *, output_root: Path) -> Frame:
        """Run one source frame, publishing ``01-input``, ``02-*``, etc."""

        output_root = Path(output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        print(f"[pipeline] input started: source={type(source).__name__}")
        try:
            with tempfile.TemporaryDirectory(
                prefix=".input-", dir=output_root
            ) as workspace:
                loaded = source.load(InputContext(Path(workspace)))
                validate_scene(loaded.frame.graph)
                frame_directory = output_root / loaded.frame.graph.frame_id
                input_directory = frame_directory / "01-input"
                image_name = _image_name(loaded.frame.image.path)
                self._publish_stage(
                    input_directory,
                    graph=loaded.frame.graph,
                    traces=loaded.traces,
                    image=(loaded.frame.image.path, image_name),
                )
            current = Frame(
                image=Image(input_directory / image_name),
                graph=loaded.frame.graph,
            )
        except Exception:
            print(f"[pipeline] input failed: source={type(source).__name__}")
            raise
        print(f"[pipeline] input finished: frame={current.graph.frame_id}")

        for ordinal, stage in enumerate(self.stages, start=2):
            label = f"{ordinal:02d}-{stage.name}"
            print(f"[pipeline] stage started: {label}")
            try:
                output = stage.run(current)
                for change in output.changes:
                    if not isinstance(change, stage.allowed_changes):
                        raise ValueError(
                            f"Stage {stage.name} cannot produce "
                            f"{type(change).__name__}"
                        )
                graph = self.change_applier.apply(
                    current.graph, output.changes
                )
                validate_scene(graph)
                self._publish_stage(
                    frame_directory / label,
                    graph=graph,
                    traces=output.traces,
                )
                current = Frame(image=current.image, graph=graph)
            except Exception:
                print(f"[pipeline] stage failed: {label}")
                raise
            print(f"[pipeline] stage finished: {label}")

        _write_graph(frame_directory / "graph.json", current.graph)
        print(f"[pipeline] finished: output={frame_directory}")
        return current

    def _publish_stage(
        self,
        destination: Path,
        *,
        graph: Scene,
        traces: Sequence[Trace],
        image: tuple[Path, str] | None = None,
    ) -> None:
        if destination.exists():
            raise FileExistsError(f"Stage output already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
        )
        try:
            graph_path = temporary / "graph.json"
            _write_graph(graph_path, graph)
            serialized_graph = Scene.model_validate_json(graph_path.read_bytes())
            stage_traces = (
                *traces,
                Trace.bytes(
                    "graph.png",
                    render_graphviz(serialized_graph),
                    media_type="image/png",
                ),
            )
            self.trace_store.publish(temporary, stage_traces)
            if image is not None:
                source, name = image
                shutil.copy2(source, temporary / name)
            temporary.replace(destination)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise


def _image_name(path: Path) -> str:
    suffix = path.suffix.lower()
    return "image" + (suffix if suffix else ".bin")


def _write_graph(path: Path, graph: Scene) -> None:
    payload = graph.model_dump(mode="json", exclude_none=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
