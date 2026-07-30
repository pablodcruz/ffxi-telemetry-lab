from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol


@dataclass(frozen=True)
class FrozenInput:
    source: str
    path: Path
    source_file: str
    byte_limit: int
    mtime_ns: int
    fingerprint_sha256: str
    timestamp_field: str
    event_type_field: Optional[str]


@dataclass(frozen=True)
class RawRecord:
    frozen_input: FrozenInput
    source_line_number: int
    raw_line: bytes


class EventSource(Protocol):
    def freeze(self) -> List[FrozenInput]:
        """Capture immutable read boundaries for one collection session."""

    def records(
        self,
        frozen_input: FrozenInput,
        start_byte: int = 0,
        start_line_number: int = 0,
    ) -> Iterable[RawRecord]:
        """Yield records without reading beyond the frozen byte boundary."""


class EventSink(Protocol):
    def existing_event_ids(self) -> set[str]:
        """Return deterministic IDs already committed by this sink."""

    def write_events(self, rows: List[Dict[str, object]], session_id: str) -> int:
        """Atomically commit event rows and return the number written."""

    def write_quarantine(self, rows: List[Dict[str, object]], session_id: str) -> int:
        """Commit malformed rows outside Bronze and return the number written."""
