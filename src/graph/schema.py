from __future__ import annotations

from functools import cache
from pathlib import Path

from linkml_runtime.utils.schemaview import SchemaView

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "scene_graph.yaml"


@cache
def schema_view() -> SchemaView:
    """Load the authoritative LinkML schema with its imports resolved."""

    return SchemaView(str(SCHEMA_PATH))
