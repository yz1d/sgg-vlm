from __future__ import annotations

from src.clients.vlm import VlmClient
from src.frame import Frame
from src.graph.changes import AddObjectState, AddRelationship
from src.stage import StageOutput


class RelationExtractionStage:
    """Proposes graph relationships and supported unary object states."""

    name = "relation-extraction"
    allowed_changes = (AddRelationship, AddObjectState)

    def __init__(self, client: VlmClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        raise NotImplementedError
