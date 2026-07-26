from __future__ import annotations

from src.clients.vlm import VlmRequest, VlmResponse
from src.config import VlmConfig


class LiteLlmClient:
    def __init__(self, config: VlmConfig) -> None:
        self.config = config

    def complete(self, request: VlmRequest) -> VlmResponse:
        raise NotImplementedError
