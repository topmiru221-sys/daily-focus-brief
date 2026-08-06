from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
RAW_ROOT = Path("data/raw")
OUTPUT_ROOT = Path("data/analysis/institutional")
LOG = logging.getLogger("analyze_institutional")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def latest_json(directory: Path) -> Path | None:
    files = sorted(
        path for path in directory.glob("*.json")
        if path.name != "latest.json"
    )
    return files[-1] if files else None


def load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def clean_key(value: Any) -> str:
    return re.sub(r"[\s()（）_\-／/及陸資外資自營商]", "", str(value or "")).lower()


def number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if text in {"", "--", "---", "N/A", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def find_value(row: dict[str, Any], patterns: list[str]) -> Any:
    normalized = {clean_key(key): value for key, value in row.items()}
    for pattern in patterns:
        target = clean_key(pattern)
        for key, value in normalized.items():
            if target and target in key:
                return value
    return None


def legacy_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    fields = payload.get("fields", [])
    rows = payload.get("data", [])
    if not isinstance(fields, list) or not isinstance(rows, list):
        return []

    result = []
    for values in rows:
        if not isinstance(values, list):
            continue
        result.append(
            {
                str(fields[index]): values[index] if index < len(values) else None
                for index in range(len(fields))
            }
        )
    return result


def normalize_row(
    row: dict[str, Any],
    market: str,
) -> dict[str, Any] | None:
    code = find_value(
        row,
        ["證券代號", "股票代號", "代號", "code", "stockno"],
    )
    name = find_value(
        row,
        ["證券名稱", "股票名稱", "名稱", "name"],
    )

    if code is None:
        return None

    foreign = number(
        find_value(
            row,
            [
                "外陸資買賣超股數不含外資自營商",
                "外資及陸資買賣超股數",
                "外資買賣超股數",
                "foreignnetbuysell",
                "foreigninvestmentnetbuysell",
            ],
        )
    )
    trust = number(
        find_value(
            row,
            [
                "投信買賣超股數",
                "investmenttrustnetbuysell",
                "trustnetbuysell",
            ],
        )
    )

    dealer_total = number(
        find_value(
            row,
            [
                "自營商買賣超股數",
                "dealernetbuysell",
            ],
        )
    )
    dealer_proprietary = number(
        find_value(
            row,
            [
                "自營商自行買賣買賣超股數",
                "dealerproprietarynetbuysell",
            ],
        )
    )
    dealer_hedge = number(
        find_value(
            row,
            [
                "自營商避險買賣超股數",
                "dealerhedgenetbuysell",
            ],
        )
    )

    if dealer_total is None:
        components = [
            value
            for value in (dealer_proprietary, dealer_hedge)
            if value is not None
        ]
        dealer_total = sum(components) if components else None

    total = number(
        find_value(
            row,
            [
                "三大法人買賣超股數",
                "totalinstitutionalnetbuysell",
                "totalnetbuysell",
            ],
        )
    )
    if total is None:
        components = [
            value for value in (foreign, trust, dealer_total)
            if value is not None
        ]
        total = sum(components) if components else None

    if all(value is None for value in (foreign, trust, dealer_total, total)):
        return None

    return {
        "market": market,
        "code": str(code).strip(),
        "name": str(name or "").strip(),
        "foreign_net_shares": foreign,
        "investment_trust_net_shares": trust,
        "dealer_net_shares": dealer_total,
        "total_institutional_net_shares": total,
    }


def extract_twse(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    report = payload.get("datasets", {}).get("institutional_detail")
    if not isinstance(report, dict):
        return []
    return [
        normalized
        for row in legacy_rows(report)
        for normalized in [normalize_row(row, "TWSE")]
        if normalized
    ]


def extract_tpex(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    rows = payload.get("datasets", {}).get("institutional_detail", [])
    if not isinstance(rows, list):
        return []
    return [
        normalized
        for row in rows
        if isinstance(row, dict)
        for normalized in [normalize_row(row, "TPEx")]
        if normalized
    ]


def ranking(
    rows: list[dict[str, Any]],
    field: str,
    *,
    descending: bool,
    limit: int = 50,
) -> list[dict[str, Any]]:
    valid = [row for row in rows if row.get(field) is not None]
    valid.sort(
        key=lambda row: row[field],
        reverse=descending,
    )

    selected = valid[:limit]
    result = []
    for rank, row in enumerate(selected, start=1):
        value = row[field]
        result.append(
            {
                "rank": rank,
                "market": row["market"],
                "code": row["code"],
                "name": row["name"],
                "net_shares": value,
                "net_lots": round(value / 1000, 3),
            }
        )
    return result


def build_analysis() -> dict[str, Any]:
    now = datetime.now(TAIPEI)
    twse_path = latest_json(RAW_ROOT / "twse")
    tpex_path = latest_json(RAW_ROOT / "tpex")
    twse = load_json(twse_path)
    tpex = load_json(tpex_path)

    rows = extract_twse(twse) + extract_tpex(tpex)
    data_dates = [
        value
        for value in [
            twse.get("official_data_date") if twse else None,
            tpex.get("data_date") if tpex else None,
        ]
        if isinstance(value, str)
    ]

    status = "ok" if rows else "pending"

    return {
        "schema_version": "2.5",
        "generated_at": now.isoformat(),
        "run_date": now.date().isoformat(),
        "data_date": max(data_dates) if data_dates else None,
        "status": status,
        "units": {
            "net_shares": "股",
            "net_lots": "張，1張=1000股",
        },
        "coverage": {
            "parsed_rows": len(rows),
            "twse_rows": sum(row["market"] == "TWSE" for row in rows),
            "tpex_rows": sum(row["market"] == "TPEx" for row in rows),
        },
        "rankings": {
            "foreign_buy_top50": ranking(
                rows, "foreign_net_shares", descending=True
            ),
            "foreign_sell_top50": ranking(
                rows, "foreign_net_shares", descending=False
            ),
            "investment_trust_buy_top50": ranking(
                rows, "investment_trust_net_shares", descending=True
            ),
            "investment_trust_sell_top50": ranking(
                rows, "investment_trust_net_shares", descending=False
            ),
            "dealer_buy_top50": ranking(
                rows, "dealer_net_shares", descending=True
            ),
            "dealer_sell_top50": ranking(
                rows, "dealer_net_shares", descending=False
            ),
        },
        "notes": (
            []
            if rows
            else ["法人明細尚未取得或官方欄位無法核對，維持待更新"]
        ),
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
        payload = build_analysis()
        path = save(payload)
        LOG.info("Institutional analysis written to %s", path)
        print(path.as_posix())
        return 0
    except Exception as exc:
        LOG.exception("Institutional analysis failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
