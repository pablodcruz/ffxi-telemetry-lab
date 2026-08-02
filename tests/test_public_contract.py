import datetime as dt
import json
from pathlib import Path

import pytest

from ffxi_telemetry import blob_publish
from ffxi_telemetry.public_contract import (
    DASHBOARD_DATASET_FIELDS,
    PUBLIC_SCHEMA_VERSION,
    build_dashboard_contract,
    validate_dashboard_contract,
)


def _complete_snapshot(generated_at: dt.datetime) -> dict[str, object]:
    datasets: dict[str, list[dict[str, object]]] = {}
    for name, fields in DASHBOARD_DATASET_FIELDS.items():
        row_count = 20 if name == "nm_status" else 1
        datasets[name] = [
            {field: f"{name}-{index}-{field}" for field in fields}
            for index in range(row_count)
        ]
    snapshot: dict[str, object] = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "privacy": {
            "classification": "public_aggregate",
            "contains_raw_payloads": False,
            "contains_agent_ids": False,
            "contains_lease_ids": False,
        },
        "datasets": datasets,
    }
    snapshot["dashboard_contract"] = build_dashboard_contract(datasets)
    return snapshot


def test_complete_dashboard_contract_accepts_every_required_dataset() -> None:
    now = dt.datetime(2026, 8, 2, 17, 0, tzinfo=dt.timezone.utc)
    snapshot = _complete_snapshot(now)

    counts = validate_dashboard_contract(snapshot, now=now)

    assert set(counts) == set(DASHBOARD_DATASET_FIELDS)
    assert counts["nm_status"] == 20


def test_dashboard_contract_rejects_a_forgotten_dataset() -> None:
    now = dt.datetime(2026, 8, 2, 17, 0, tzinfo=dt.timezone.utc)
    snapshot = _complete_snapshot(now)
    del snapshot["datasets"]["combat_daily"]  # type: ignore[index]

    with pytest.raises(ValueError, match="combat_daily"):
        validate_dashboard_contract(snapshot, now=now)


def test_dashboard_contract_rejects_stale_publication() -> None:
    now = dt.datetime(2026, 8, 2, 17, 0, tzinfo=dt.timezone.utc)
    snapshot = _complete_snapshot(now - dt.timedelta(hours=1))

    with pytest.raises(ValueError, match="stale at publish time"):
        validate_dashboard_contract(snapshot, now=now)


def test_publish_verifies_the_remote_object_byte_for_byte(
    tmp_path: Path,
    monkeypatch,
) -> None:
    snapshot = _complete_snapshot(dt.datetime.now(dt.timezone.utc))
    snapshot_path = tmp_path / "latest.json"
    raw = json.dumps(snapshot, sort_keys=True).encode()
    snapshot_path.write_bytes(raw)

    class Response:
        is_error = False
        status_code = 200

        def __init__(self, content: bytes, payload: dict[str, object]) -> None:
            self.content = content
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    monkeypatch.setattr(
        blob_publish.httpx,
        "put",
        lambda *args, **kwargs: Response(b"", {"url": "https://blob.test/latest.json"}),
    )
    monkeypatch.setattr(
        blob_publish.httpx,
        "get",
        lambda *args, **kwargs: Response(raw, snapshot),
    )

    result = blob_publish.publish_public_snapshot(snapshot_path, token="test-token")

    assert result["verified_remote"] is True
    assert result["dataset_rows"]["combat_daily"] == 1
    assert len(result["sha256"]) == 64


def test_publish_rejects_a_remote_object_that_does_not_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    snapshot = _complete_snapshot(dt.datetime.now(dt.timezone.utc))
    snapshot_path = tmp_path / "latest.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    class Response:
        is_error = False
        status_code = 200
        content = b"different"

        def json(self) -> dict[str, object]:
            return {"url": "https://blob.test/latest.json"}

    monkeypatch.setattr(blob_publish.httpx, "put", lambda *args, **kwargs: Response())
    monkeypatch.setattr(blob_publish.httpx, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(blob_publish.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="different snapshot"):
        blob_publish.publish_public_snapshot(snapshot_path, token="test-token")
