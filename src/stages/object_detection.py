from __future__ import annotations

from src.clients.vlm import VlmClient
from src.frame import Frame
from src.graph.changes import AddRoadUser, RefineRoadUserType
from src.stage import StageOutput


class ObjectDetectionStage:
    """Proposes additions and compatible type refinements for road users."""

    name = "object-detection"
    allowed_changes = (AddRoadUser, RefineRoadUserType)

    def __init__(self, client: VlmClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        raise NotImplementedError
