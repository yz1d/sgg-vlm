from __future__ import annotations

import hashlib
import json
import shutil
import subprocess

from src.graph._generated.models import RoadObject, Scene, StaticObject


class GraphvizError(RuntimeError):
    """The Graphviz renderer is unavailable or failed."""


def graph_to_dot(graph: Scene) -> str:
    """Render a compact DOT overview of a normalized scene graph."""

    def quoted(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    palette = (
        "#ffb3a7",
        "#9fe2df",
        "#ffe48a",
        "#a9d8f5",
        "#ddb4e9",
        "#b8e6b8",
        "#ffc5a8",
        "#bad8e8",
    )

    def color_for(type_name: str) -> str:
        digest = hashlib.sha256(type_name.encode("utf-8")).digest()
        return palette[int.from_bytes(digest[:2], "big") % len(palette)]

    graph_label = graph.frame_id
    if graph.weather is not None:
        graph_label += f"\nweather: {graph.weather}"

    lines = [
        "digraph scene_graph {",
        f"  graph [label={quoted(graph_label)}, labelloc=t, rankdir=TB, "
        'bgcolor="white", pad=0.25, nodesep=0.45, ranksep=0.8, '
        "splines=true, outputorder=edgesfirst];",
        '  node [shape=ellipse, style=filled, color="black", penwidth=1.2, '
        'fontname="Helvetica", fontsize=12, margin="0.14,0.08"];',
        '  edge [color="black", fontcolor="black", penwidth=1.1, '
        'fontname="Helvetica", fontsize=11, arrowsize=0.8];',
    ]

    ego = next(object_ for object_ in graph.objects if object_.id == "ego")
    ego_label = f"ego\n{ego.type}"
    lines.extend(
        [
            f'  "ego" [label={quoted(ego_label)}, fillcolor="#ff6b6b"];',
            '  { rank=min; "ego"; }',
        ]
    )

    non_ego_objects = sorted(
        (object_ for object_ in graph.objects if object_.id != "ego"),
        key=lambda object_: object_.id,
    )
    for object_ in non_ego_objects:
        label = f"{object_.id}\n{object_.type}"
        attributes = object_.model_dump(
            mode="json",
            exclude={"id", "type", "bbox", "track_id", "provenance"},
            exclude_none=True,
        )
        for name, value in attributes.items():
            label += f"\n{name}={value}"
        shape = "box" if isinstance(object_, RoadObject) else "ellipse"
        if isinstance(object_, StaticObject):
            shape = "diamond"
        lines.append(
            f"  {quoted(object_.id)} "
            f"[label={quoted(label)}, shape={shape}, "
            f"fillcolor={quoted(color_for(object_.type))}];"
        )

    relations_by_pair: dict[tuple[str, str], list[str]] = {}
    for relation in graph.relations:
        relations_by_pair.setdefault((relation.subject, relation.object), []).append(
            relation.type
        )

    visible_object_ids = [
        object_.id
        for object_ in non_ego_objects
        if object_.bbox is not None
    ]
    if visible_object_ids:
        lines.append(
            f"  {{ rank=same; "
            f"{'; '.join(quoted(item) for item in visible_object_ids)}; }}"
        )
        connected_to_ego = {
            object_ if subject == "ego" else subject
            for subject, object_ in relations_by_pair
            if subject == "ego" or object_ == "ego"
        }
        for object_id in visible_object_ids:
            if object_id not in connected_to_ego:
                lines.append(
                    f'  "ego" -> {quoted(object_id)} '
                    "[style=invis, weight=100];"
                )

    road_object_ids = [
        object_.id
        for object_ in non_ego_objects
        if isinstance(object_, RoadObject) and object_.bbox is None
    ]
    if road_object_ids:
        lines.append(
            f"  {{ rank=max; "
            f"{'; '.join(quoted(item) for item in road_object_ids)}; }}"
        )

    for (subject, object_), relation_types in sorted(relations_by_pair.items()):
        label = "\n".join(dict.fromkeys(relation_types))
        if object_ == "ego":
            lines.append(
                f'  "ego" -> {quoted(subject)} '
                f"[label={quoted(label)}, dir=back, weight=10];"
            )
        else:
            lines.append(
                f"  {quoted(subject)} -> {quoted(object_)} "
                f"[label={quoted(label)}];"
            )

    lines.append("}")
    return "\n".join(lines) + "\n"


def render_graphviz(graph: Scene) -> bytes:
    """Render a scene graph to PNG using the Graphviz `dot` executable."""

    dot = shutil.which("dot")
    if dot is None:
        raise GraphvizError("Graphviz 'dot' executable is required")
    try:
        result = subprocess.run(
            [dot, "-Tpng"],
            input=graph_to_dot(graph).encode("utf-8"),
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise GraphvizError(f"Graphviz execution failed: {exc}") from exc
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise GraphvizError(message or "Graphviz rendering failed")
    return result.stdout
