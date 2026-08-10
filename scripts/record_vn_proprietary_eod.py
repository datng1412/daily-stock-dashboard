"""Record one user-verified HOSE proprietary-flow EOD aggregate.

This CLI hashes an optional PDF but never parses, copies, downloads, or OCRs it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.services.vietnam_proprietary_flow_eod_service import (  # noqa: E402
    ProprietaryFlowValidationError,
    VietnamProprietaryFlowEodService,
)
from src.services.vietnam_proprietary_flow_eod_store import (  # noqa: E402
    ProprietaryFlowConflictError,
    ProprietaryFlowStoreError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record verified manual HOSE proprietary-flow EOD data")
    parser.add_argument("--date", required=True)
    parser.add_argument("--exchange", required=True)
    parser.add_argument("--buy-value", required=True, type=int)
    parser.add_argument("--sell-value", required=True, type=int)
    parser.add_argument("--net-value", type=int)
    parser.add_argument("--buy-volume", type=int)
    parser.add_argument("--sell-volume", type=int)
    parser.add_argument("--net-volume", type=int)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-file")
    parser.add_argument("--source-file-unavailable", action="store_true")
    parser.add_argument("--source-title")
    parser.add_argument("--verified-by-user", action="store_true")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--dry-run", action="store_true")
    operation.add_argument("--persist", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--replacement-reason")
    parser.add_argument("--json", action="store_true")
    return parser


def _candidate(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "trading_date": args.date,
        "exchange": args.exchange,
        "buy_value": args.buy_value,
        "sell_value": args.sell_value,
        "net_value": args.net_value,
        "buy_volume": args.buy_volume,
        "sell_volume": args.sell_volume,
        "net_volume": args.net_volume,
        "source_url": args.source_url,
        "source_file": args.source_file,
        "source_file_unavailable": args.source_file_unavailable,
        "source_title": args.source_title,
        "verified_by_user": args.verified_by_user,
    }


def run(argv: list[str] | None = None, *, service: VietnamProprietaryFlowEodService | None = None) -> tuple[int, dict[str, Any]]:
    args = build_parser().parse_args(argv)
    owner = service or VietnamProprietaryFlowEodService()
    try:
        if args.dry_run:
            result = owner.preview_candidate(**_candidate(args))
        else:
            result = owner.persist_candidate(
                **_candidate(args),
                replace=args.replace,
                replacement_reason=args.replacement_reason,
            )
        return 0, result
    except (ProprietaryFlowValidationError, ProprietaryFlowConflictError, ProprietaryFlowStoreError) as exc:
        return 2, {"operation": "persist" if args.persist else "dry_run", "accepted": False, "error": str(exc)}


def main(argv: list[str] | None = None) -> int:
    code, result = run(argv)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
