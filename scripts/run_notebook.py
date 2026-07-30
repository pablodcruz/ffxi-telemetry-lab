from __future__ import annotations

from pathlib import Path

import nbformat
from build_notebook import build
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    source = build()
    notebook = nbformat.read(source, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=180,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    )
    executed = client.execute(cwd=str(ROOT))
    destination = ROOT / "artifacts" / "notebooks" / "ffxi_telemetry_analysis.executed.ipynb"
    destination.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(executed, destination)
    print(destination)


if __name__ == "__main__":
    main()
