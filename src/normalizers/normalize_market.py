from __future__ import annotations

import json
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
RAW_ROOT = Path("data/raw")
OUTPUT_ROOT = Path("data/normalized")
LOG = logging.getLogger("normalize_market")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def latest_file(directory: Path) -> Path | None:
    files = sorted(directory.glob("*.json"))
    return files[-1] if files else None


def load_json(path: Path | None) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, "source file not found"

    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return None, "source file is empty"
        payload = json.loads(text)
        if not isinstance(payload, dict):
            return None, "source payload is not an object"
        return payload, None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def roc_to_iso(value: Any) -> str | None:
    text = re.sub(r"\D", "", str(value or ""))
    if len(text) != 7:
        return None

    try:
        year = int(text[:3]) + 1911
        month = int(text[3:5])
        day = int(text[5:7])
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if text in {"", "--", "---", "N/A", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def latest_twse_market(payload: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "pending",
        "data_date": None,
        "index_close": None,
        "index_change": None,
        "trade_value_twd": None,
        "trade_volume": None,
        "transactions": None,
        "source_status": None,
        "source_errors": {},
    }

    if not payload:
        return result

    result["source_status"] = payload.get("status")
    result["source_errors"] = payload.get("errors", {})

    rows = payload.get("datasets", {}).get("market_summary", [])
    if not isinstance(rows, list) or not rows:
        return result

    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        iso_date = roc_to_iso(row.get("Date"))
        if iso_date:
            candidates.append((iso_date, row))

    if not candidates:
        return result

    data_date, row = max(candidates, key=lambda item: item[0])
    result.update(
        {
            "status": "ok",
            "data_date": data_date,
            "index_close": number(row.get("TAIEX")),
            "index_change": number(row.get("Change")),
            "trade_value_twd": number(row.get("TradeValue")),
            "trade_volume": number(row.get("TradeVolume")),
            "transactions": number(row.get("Transaction")),
        }
    )
    return result


def source_summary(
    name: str,
    path: Path | None,
    payload: dict[str, Any] | None,
    error: str | None,
) -> dict[str, Any]:
    if error:
        return {
            "name": name,
            "status": "pending",
            "file": path.as_posix() if path else None,
            "error": error,
        }

    return {
        "name": name,
        "status": payload.get("status", "unknown") if payload else "pending",
        "file": path.as_posix() if path else None,
        "generated_at": payload.get("generated_at") if payload else None,
        "snapshot_date": (
            payload.get("data_date") or payload.get("snapshot_date")
            if payload
            else None
        ),
        "errors": payload.get("errors", {}) if payload else {},
    }


def build_normalized() -> dict[str, Any]:
    now = datetime.now(TAIPEI)

    source_paths = {
        name: latest_file(RAW_ROOT / name)
        for name in ("twse", "tpex", "taifex")
    }

    loaded = {
        name: load_json(path)
        for name, path in source_paths.items()
    }

    twse_payload, _ = loaded["twse"]
    twse_market = latest_twse_market(twse_payload)

    official_dates = [
        value
        for value in [twse_market.get("data_date")]
        if isinstance(value, str)
    ]
    official_data_date = max(official_dates) if official_dates else None

    freshness = "pending"
    if official_data_date:
        freshness = (
            "current"
            if official_data_date == now.date().isoformat()
            else "delayed"
        )

    return {
        "schema_version": "2.4",
        "generated_at": now.isoformat(),
        "run_date": now.date().isoformat(),
        "official_data_date": official_data_date,
        "freshness": freshness,
        "market": {
            "twse": twse_market,
            "tpex": {
                "status": "pending",
                "note": "待下一階段依實際 TPEx 欄位標準化",
            },
        },
        "derivatives": {
            "taifex": {
                "status": "pending",
                "note": "待下一階段依實際 TAIFEX 欄位標準化",
            }
        },
        "sources": {
            name: source_summary(name, source_paths[name], *loaded[name])
            for name in ("twse", "tpex", "taifex")
        },
        "warnings": [
            warning
            for warning in [
                (
                    "官方最新資料日期晚於執行日期，標示為延遲資料"
                    if freshness == "delayed"
                    else None
                ),
                (
                    "TWSE 法人資料尚未完整取得"
                    if twse_market.get("source_errors")
                    else None
                ),
            ]
            if warning
        ],
    }


def save(payload: dict[str, Any]) -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    run_date = payload["run_date"]
    output_path = OUTPUT_ROOT / f"{run_date}.json"
    latest_path = OUTPUT_ROOT / "latest.json"

    content = json.dumps(payload, ensure_ascii=False, indent=2)
    output_path.write_text(content, encoding="utf-8")
    latest_path.write_text(content, encoding="utf-8")
    return output_path


def main() -> int:
    setup_logging()
    try:
        payload = build_normalized()
        path = save(payload)
        LOG.info("Normalized market snapshot written to %s", path)
        print(path.as_posix())
        return 0
    except Exception as exc:
        LOG.exception("Normalization failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
