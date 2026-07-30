from __future__ import annotations

import hashlib


def deterministic_event_id(
    source_relative_path: str,
    source_line_number: int,
    raw_line: bytes,
) -> str:
    digest = hashlib.sha256()
    digest.update(source_relative_path.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(str(source_line_number).encode("ascii"))
    digest.update(b"\x00")
    digest.update(raw_line)
    return digest.hexdigest()
