from __future__ import annotations

from src.clients.vlm import VlmClient
from src.frame import Frame
from src.graph.changes import AddRoadUser
from src.stage import StageOutput


class ObjectDetectionStage:
    """Proposes new road users observed in the frame."""

    name = "object-detection"
    allowed_changes = (AddRoadUser,)

    def __init__(self, client: VlmClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        raise NotImplementedError
