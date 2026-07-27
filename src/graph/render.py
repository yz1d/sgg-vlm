from __future__ import annotations

import hashlib
import json
import shutil
import subprocess

from src.graph.models import Scene


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

    lines = [
        "digraph scene_graph {",
        f"  graph [label={quoted(graph.frame_id)}, labelloc=t, rankdir=TB, "
        'bgcolor="white", pad=0.25, nodesep=0.45, ranksep=0.8, '
        "splines=true, outputorder=edgesfirst];",
        '  node [shape=ellipse, style=filled, color="black", penwidth=1.2, '
        'fontname="Helvetica", fontsize=12, margin="0.14,0.08"];',
        '  edge [color="black", fontcolor="black", penwidth=1.1, '
        'fontname="Helvetica", fontsize=11, arrowsize=0.8];',
        '  "ego" [label="ego\\nEgoVehicle", fillcolor="#ff6b6b"];',
        '  { rank=min; "ego"; }',
    ]

    states_by_subject: dict[str, list[str]] = {}
    for state in graph.states or []:
        values = state.model_dump(
            mode="json",
            exclude={"type", "subject", "confidence", "provenance"},
            exclude_none=True,
        )
        detail = ", ".join(f"{name}={value}" for name, value in values.items())
        label = state.type + (f": {detail}" if detail else "")
        states_by_subject.setdefault(state.subject, []).append(label)

    road_users = sorted(graph.road_users or [], key=lambda road_user: road_user.id)
    for road_user in road_users:
        label = f"{road_user.id}\n{road_user.type}"
        for state in states_by_subject.get(road_user.id, []):
            label += f"\n[{state}]"
        lines.append(
            f"  {quoted(road_user.id)} "
            f"[label={quoted(label)}, fillcolor={quoted(color_for(road_user.type))}];"
        )

    relations_by_pair: dict[tuple[str, str], list[str]] = {}
    for relationship in graph.relationships or []:
        relations_by_pair.setdefault(
            (relationship.subject, relationship.object), []
        ).append(relationship.type)

    road_user_ids = [road_user.id for road_user in road_users]
    if road_user_ids:
        lines.append(
            f"  {{ rank=same; {'; '.join(quoted(item) for item in road_user_ids)}; }}"
        )
        connected_to_ego = {
            object_ if subject == "ego" else subject
            for subject, object_ in relations_by_pair
            if subject == "ego" or object_ == "ego"
        }
        for road_user_id in road_user_ids:
            if road_user_id not in connected_to_ego:
                lines.append(
                    f'  "ego" -> {quoted(road_user_id)} '
                    "[style=invis, weight=100];"
                )

    for (subject, object_), relationship_types in sorted(relations_by_pair.items()):
        label = "\n".join(dict.fromkeys(relationship_types))
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
    result = subprocess.run(
        [dot, "-Tpng"],
        input=graph_to_dot(graph).encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise GraphvizError(message or "Graphviz rendering failed")
    return result.stdout
