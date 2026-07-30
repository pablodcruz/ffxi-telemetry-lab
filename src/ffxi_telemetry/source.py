from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .contracts import FrozenInput, RawRecord


@dataclass(frozen=True)
class SourceSpec:
    name: str
    relative_glob: str
    timestamp_field: str
    event_type_field: Optional[str]


ALLOWED_SOURCE_SPECS: Sequence[SourceSpec] = (
    SourceSpec(
        name="agent_actions",
        relative_glob="runtime/audit/agent-actions.jsonl",
        timestamp_field="timestamp",
        event_type_field="operation",
    ),
    SourceSpec(
        name="farm_supervisor",
        relative_glob="runtime/farm-supervisor/*.log",
        timestamp_field="at",
        event_type_field="event",
    ),
    SourceSpec(
        name="navigation",
        relative_glob="runtime/navigation/collision-probes.jsonl",
        timestamp_field="timestamp",
        event_type_field=None,
    ),
)


def _hash_prefix(path: Path, byte_limit: int) -> str:
    digest = hashlib.sha256()
    remaining = byte_limit
    with path.open("rb") as handle:
        while remaining:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    if remaining:
        raise RuntimeError(f"source changed while freezing: {path}")
    return digest.hexdigest()


class AllowlistedJsonlSource:
    def __init__(self, source_root: Path):
        self.source_root = source_root.resolve()

    def _validate_path(self, path: Path) -> Path:
        if path.is_symlink():
            raise ValueError(f"refusing symlinked telemetry source: {path}")
        resolved = path.resolve()
        try:
            resolved.relative_to(self.source_root)
        except ValueError as exc:
            raise ValueError(f"source escaped configured root: {path}") from exc
        if not resolved.is_file():
            raise ValueError(f"telemetry source is not a regular file: {path}")
        return resolved

    def freeze(self) -> List[FrozenInput]:
        frozen: List[FrozenInput] = []
        for spec in ALLOWED_SOURCE_SPECS:
            for candidate in sorted(self.source_root.glob(spec.relative_glob)):
                path = self._validate_path(candidate)
                stat = path.stat()
                relative = path.relative_to(self.source_root).as_posix()
                frozen.append(
                    FrozenInput(
                        source=spec.name,
                        path=path,
                        source_file=relative,
                        byte_limit=stat.st_size,
                        mtime_ns=stat.st_mtime_ns,
                        fingerprint_sha256=_hash_prefix(path, stat.st_size),
                        timestamp_field=spec.timestamp_field,
                        event_type_field=spec.event_type_field,
                    )
                )
        return frozen

    def records(
        self,
        frozen_input: FrozenInput,
        start_byte: int = 0,
        start_line_number: int = 0,
    ) -> Iterable[RawRecord]:
        if start_byte < 0 or start_byte > frozen_input.byte_limit:
            raise ValueError("start byte falls outside frozen input")
        with frozen_input.path.open("rb") as handle:
            handle.seek(start_byte)
            line_number = start_line_number
            while handle.tell() < frozen_input.byte_limit:
                remaining = frozen_input.byte_limit - handle.tell()
                raw_line = handle.readline(remaining)
                if not raw_line:
                    break
                line_number += 1
                yield RawRecord(
                    frozen_input=frozen_input,
                    source_line_number=line_number,
                    raw_line=raw_line,
                )
