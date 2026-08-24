from __future__ import annotations

import json
import sys
from pathlib import Path


STATUS_PATH = Path("data/history/prices/_status.json")


def main() -> int:
    if not STATUS_PATH.exists():
        print("Priority history validation FAILED: status file is missing")
        return 1

    try:
        status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Priority history validation FAILED: unreadable status file: {exc}")
        return 1

    requested = int(status.get("requested_codes") or 0)
    succeeded = int(status.get("success_count") or 0)
    failed = int(status.get("failed_count") or 0)
    if status.get("mode") != "priority":
        print("Priority history validation FAILED: unexpected backfill mode")
        return 1
    if requested <= 0:
        print("Priority history validation OK: no incomplete priority stocks remain")
        return 0
    if succeeded <= 0:
        print(f"Priority history validation FAILED: 0/{requested} stocks succeeded")
        return 1

    print(
        "Priority history validation OK: "
        f"requested={requested}, succeeded={succeeded}, failed={failed}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
