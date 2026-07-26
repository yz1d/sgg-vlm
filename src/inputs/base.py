from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol

from src.frame import Frame
from src.traces import Trace


@dataclass(frozen=True, slots=True)
class InputOutput:
    """One seeded frame and traces for its ``01-input`` publication."""

    frame: Frame
    traces: tuple[Trace, ...] = ()


class InputSource(Protocol):
    name: str

    def frames(self) -> Iterator[InputOutput]: ...
