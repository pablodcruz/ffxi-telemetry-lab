from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

from dotenv import load_dotenv

from .collector import collect
from .config import Settings
from .hourly_refresh import refresh_public_metrics
from .mariadb_snapshot import TABLE_CATALOG, snapshot_tables
from .observer import observe_forever, sample_state
from .public_export import export_public_snapshot
from .warehouse import prepare_warehouse


def _common_source_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source-root",
        help="Read-only FFXI Agent Lab repository root; may also use FFXI_SOURCE_ROOT",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ffxi-telemetry")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backfill = subparsers.add_parser("backfill", help="Full historical, idempotent backfill")
    _common_source_argument(backfill)
    backfill.add_argument("--data-dir")

    incremental = subparsers.add_parser(
        "collect",
        help="Incremental collection with observed-at-ingestion Git attribution",
    )
    _common_source_argument(incremental)
    incremental.add_argument("--data-dir")

    prepare = subparsers.add_parser("prepare-warehouse", help="Refresh DuckDB Bronze views")
    prepare.add_argument("--data-dir")
    prepare.add_argument("--duckdb-path")

    observe = subparsers.add_parser("observe", help="Sample supervisor state read-only")
    _common_source_argument(observe)
    observe.add_argument("--data-dir")
    observe.add_argument("--interval-seconds", type=float)
    observe.add_argument("--once", action="store_true")

    mariadb = subparsers.add_parser(
        "snapshot-mariadb",
        help="Snapshot reviewed tables with a dedicated read-only account",
    )
    _common_source_argument(mariadb)
    mariadb.add_argument("--data-dir")
    mariadb.add_argument(
        "--tables",
        nargs="+",
        choices=sorted(TABLE_CATALOG),
        required=True,
    )

    public = subparsers.add_parser(
        "export-public",
        help="Write a reviewed aggregate-only dashboard snapshot",
    )
    public.add_argument("--duckdb-path")
    public.add_argument("--output", default="dashboard/public_snapshot.json")
    public.add_argument(
        "--site-output",
        help="Optional mirrored public aggregate snapshot for the static site",
    )

    refresh = subparsers.add_parser(
        "refresh-public",
        help="Collect, rebuild Gold, export, and publish one reviewed public snapshot",
    )
    _common_source_argument(refresh)
    refresh.add_argument("--data-dir")
    refresh.add_argument("--duckdb-path")
    refresh.add_argument("--output", default="data/public/latest.json")
    refresh.add_argument(
        "--blob-pathname",
        default=os.getenv("TELEMETRY_BLOB_PATHNAME", "telemetry/latest.json"),
    )
    refresh.add_argument(
        "--no-upload",
        action="store_true",
        help="Build the public snapshot locally without uploading it",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    load_dotenv()
    load_dotenv(".env.vercel", override=False)
    args = build_parser().parse_args(argv)
    try:
        settings = Settings.from_env(
            source_root=getattr(args, "source_root", None),
            data_dir=getattr(args, "data_dir", None),
            duckdb_path=getattr(args, "duckdb_path", None),
            observer_interval_seconds=getattr(args, "interval_seconds", None),
        )
        if args.command == "backfill":
            result = collect(
                settings.require_source_root(),
                settings.data_dir,
                historical=True,
                full_scan=True,
            )
        elif args.command == "collect":
            result = collect(
                settings.require_source_root(),
                settings.data_dir,
                historical=False,
                full_scan=False,
            )
        elif args.command == "prepare-warehouse":
            result = prepare_warehouse(settings.data_dir, settings.duckdb_path)
        elif args.command == "observe":
            if args.once:
                result = sample_state(settings.require_source_root(), settings.data_dir)
            else:
                observe_forever(
                    settings.require_source_root(),
                    settings.data_dir,
                    settings.observer_interval_seconds,
                )
                return 0
        elif args.command == "snapshot-mariadb":
            result = snapshot_tables(
                settings.require_source_root(),
                settings.data_dir,
                args.tables,
            )
        elif args.command == "export-public":
            result = export_public_snapshot(
                settings.duckdb_path,
                args.output,
                args.site_output,
            )
        elif args.command == "refresh-public":
            result = refresh_public_metrics(
                settings.require_source_root(),
                settings.data_dir,
                settings.duckdb_path,
                Path(args.output).expanduser().resolve(),
                upload=not args.no_upload,
                blob_pathname=args.blob_pathname,
            )
        else:
            raise ValueError(f"unknown command: {args.command}")
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
