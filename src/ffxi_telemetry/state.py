from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict


class CollectorState:
    def __init__(self, data_dir: Path):
        self.state_dir = data_dir / ".state"
        self.path = self.state_dir / "collector_offsets.json"
        self.manifest_dir = self.state_dir / "manifests"

    def load(self) -> Dict[str, Dict[str, object]]:
        if not self.path.exists():
            return {}
        with self.path.open(encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}

    def save(self, offsets: Dict[str, Dict[str, object]]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(offsets, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, self.path)

    def save_manifest(self, session_id: str, manifest: Dict[str, object]) -> Path:
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        path = self.manifest_dir / f"{session_id}.json"
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
        return path
