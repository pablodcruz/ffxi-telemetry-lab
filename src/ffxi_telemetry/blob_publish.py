from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

import httpx

from .public_contract import validate_dashboard_contract

FORBIDDEN_PUBLIC_KEYS = {
    "agent_id",
    "lease_id",
    "raw_json",
    "raw_payload",
    "stream_key",
    "bridge_token",
}


def validate_public_snapshot(snapshot: Dict[str, object]) -> Dict[str, int]:
    privacy = snapshot.get("privacy")
    if not isinstance(privacy, dict):
        raise ValueError("public snapshot is missing its privacy contract")
    expected = {
        "classification": "public_aggregate",
        "contains_raw_payloads": False,
        "contains_agent_ids": False,
        "contains_lease_ids": False,
    }
    for key, value in expected.items():
        if privacy.get(key) != value:
            raise ValueError(f"public snapshot privacy contract failed: {key}")

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if str(key).lower() in FORBIDDEN_PUBLIC_KEYS:
                    raise ValueError(f"forbidden public snapshot field: {key}")
                inspect(nested)
        elif isinstance(value, list):
            for nested in value:
                inspect(nested)

    inspect(snapshot.get("datasets"))
    return validate_dashboard_contract(snapshot)


def _verify_uploaded_snapshot(url: str, expected: bytes) -> None:
    expected_digest = hashlib.sha256(expected).digest()
    last_status: Optional[int] = None
    for attempt in range(6):
        separator = "&" if "?" in url else "?"
        verification_url = f"{url}{separator}verify={uuid.uuid4().hex}"
        response = httpx.get(
            verification_url,
            headers={"accept": "application/json", "cache-control": "no-cache"},
            timeout=30,
        )
        last_status = response.status_code
        if not response.is_error and hashlib.sha256(response.content).digest() == expected_digest:
            remote = response.json()
            if not isinstance(remote, dict):
                raise RuntimeError("Vercel Blob verification did not return an object")
            validate_public_snapshot(remote)
            return
        if attempt < 5:
            time.sleep(min(0.5 * (2**attempt), 5.0))

    if last_status is not None and last_status >= 400:
        raise RuntimeError(f"Vercel Blob verification failed with HTTP {last_status}")
    raise RuntimeError("Vercel Blob verification returned a different snapshot")


def publish_public_snapshot(
    snapshot_path: Path,
    pathname: str = "telemetry/latest.json",
    token: Optional[str] = None,
) -> Dict[str, object]:
    raw = snapshot_path.read_bytes()
    snapshot = json.loads(raw)
    if not isinstance(snapshot, dict):
        raise ValueError("public snapshot root must be an object")
    dataset_rows = validate_public_snapshot(snapshot)

    resolved_token = token or os.getenv("BLOB_READ_WRITE_TOKEN")
    if not resolved_token:
        raise ValueError(
            "BLOB_READ_WRITE_TOKEN is required to publish the public snapshot"
        )

    response = httpx.put(
        "https://vercel.com/api/blob",
        params={"pathname": pathname},
        content=raw,
        headers={
            "authorization": f"Bearer {resolved_token}",
            "x-api-blob-request-id": str(uuid.uuid4()),
            "x-api-blob-request-attempt": "0",
            "x-api-version": "11",
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "1",
            "x-cache-control-max-age": "300",
            "x-content-type": "application/json",
        },
        timeout=30,
    )
    if response.is_error:
        raise RuntimeError(
            f"Vercel Blob upload failed with HTTP {response.status_code}"
        )
    uploaded = response.json()
    url = uploaded.get("url")
    if not url:
        raise RuntimeError("Vercel Blob upload did not return a public URL")
    _verify_uploaded_snapshot(str(url), raw)
    return {
        "pathname": pathname,
        "url": str(url),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "verified_remote": True,
        "dataset_rows": dataset_rows,
        "generated_at": snapshot.get("generated_at"),
    }
