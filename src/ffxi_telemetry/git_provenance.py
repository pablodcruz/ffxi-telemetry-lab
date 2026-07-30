from __future__ import annotations

import bisect
import datetime as dt
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


def _parse_iso8601(value: str) -> Optional[dt.datetime]:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def observed_head(source_root: Path) -> Optional[str]:
    result = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and len(value) == 40 else None


@dataclass(frozen=True)
class CommitResolver:
    timestamps: List[dt.datetime]
    shas: List[str]

    @classmethod
    def from_repository(cls, source_root: Path) -> "CommitResolver":
        result = subprocess.run(
            ["git", "-C", str(source_root), "log", "--all", "--format=%H%x09%cI"],
            check=False,
            capture_output=True,
            text=True,
        )
        commits: List[Tuple[dt.datetime, str]] = []
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                try:
                    sha, timestamp = line.split("\t", 1)
                except ValueError:
                    continue
                parsed = _parse_iso8601(timestamp)
                if parsed and len(sha) == 40:
                    commits.append((parsed, sha))
        commits.sort(key=lambda item: item[0])
        return cls(
            timestamps=[item[0] for item in commits],
            shas=[item[1] for item in commits],
        )

    def at_or_before(self, event_time: Optional[str]) -> Optional[str]:
        parsed = _parse_iso8601(event_time or "")
        if parsed is None or not self.timestamps:
            return None
        index = bisect.bisect_right(self.timestamps, parsed) - 1
        return self.shas[index] if index >= 0 else None
