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


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value or "").lower())


def number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if text in {"", "--", "---", "N/A", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def exact_or_contains(row: dict[str, Any], candidates: list[str]) -> Any:
    normalized = {normalize_key(k): v for k, v in row.items()}

    for candidate in candidates:
        key = normalize_key(candidate)
        if key in normalized:
            return normalized[key]

    for candidate in candidates:
        key = normalize_key(candidate)
        for existing, value in normalized.items():
            if key and key in existing:
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
        result.append({
            str(fields[i]): values[i] if i < len(values) else None
            for i in range(len(fields))
        })
    return result


def normalize_twse(row: dict[str, Any]) -> dict[str, Any] | None:
    code = exact_or_contains(row, ["證券代號", "股票代號"])
    name = exact_or_contains(row, ["證券名稱", "股票名稱"])

    foreign = number(exact_or_contains(row, [
        "外陸資買賣超股數(不含外資自營商)",
        "外資及陸資買賣超股數",
    ]))
    trust = number(exact_or_contains(row, ["投信買賣超股數"]))
    dealer = number(exact_or_contains(row, ["自營商買賣超股數"]))
    total = number(exact_or_contains(row, ["三大法人買賣超股數"]))

    if code is None:
        return None

    if dealer is None:
        proprietary = number(exact_or_contains(row, ["自營商自行買賣買賣超股數"]))
        hedge = number(exact_or_contains(row, ["自營商避險買賣超股數"]))
        parts = [v for v in (proprietary, hedge) if v is not None]
        dealer = sum(parts) if parts else None

    if total is None:
        parts = [v for v in (foreign, trust, dealer) if v is not None]
        total = sum(parts) if parts else None

    return build_row("TWSE", code, name, foreign, trust, dealer, total)


def normalize_tpex(row: dict[str, Any]) -> dict[str, Any] | None:
    code = exact_or_contains(row, [
        "SecuritiesCompanyCode",
        "SecurityCode",
        "Code",
        "股票代號",
        "代號",
    ])
    name = exact_or_contains(row, [
        "CompanyName",
        "SecurityName",
        "Name",
        "股票名稱",
        "名稱",
    ])

    foreign = number(exact_or_contains(row, [
        "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Difference",
        "ForeignInvestorsincludeMainlandAreaInvestorsForeignDealersexcludedTotalDifference",
        "ForeignInvestorsTotalDifference",
        "ForeignNetBuySell",
        "外資及陸資買賣超股數",
    ]))
    trust = number(exact_or_contains(row, [
        "Securities Investment Trust Companies-Total Difference",
        "SecuritiesInvestmentTrustCompaniesTotalDifference",
        "InvestmentTrustTotalDifference",
        "InvestmentTrustNetBuySell",
        "投信買賣超股數",
    ]))
    dealer = number(exact_or_contains(row, [
        "Dealers-Total Difference",
        "DealersTotalDifference",
        "DealerTotalDifference",
        "DealerNetBuySell",
        "自營商買賣超股數",
    ]))
    total = number(exact_or_contains(row, [
        "Total Difference",
        "TotalDifference",
        "TotalNetBuySell",
        "三大法人買賣超股數",
    ]))

    if code is None:
        return None

    if total is None:
        parts = [v for v in (foreign, trust, dealer) if v is not None]
        total = sum(parts) if parts else None

    return build_row("TPEx", code, name, foreign, trust, dealer, total)


def build_row(
    market: str,
    code: Any,
    name: Any,
    foreign: float | None,
    trust: float | None,
    dealer: float | None,
    total: float | None,
) -> dict[str, Any] | None:
    if all(v is None for v in (foreign, trust, dealer, total)):
        return None

    return {
        "market": market,
        "code": str(code).strip(),
        "name": str(name or "").strip(),
        "foreign_net_shares": foreign,
        "investment_trust_net_shares": trust,
        "dealer_net_shares": dealer,
        "total_institutional_net_shares": total,
    }


def extract_twse(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    report = payload.get("datasets", {}).get("institutional_detail")
    if not isinstance(report, dict):
        return []
    return [
        item
        for row in legacy_rows(report)
        for item in [normalize_twse(row)]
        if item
    ]


def extract_tpex(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    rows = payload.get("datasets", {}).get("institutional_detail", [])
    if not isinstance(rows, list):
        return []
    return [
        item
        for row in rows
        if isinstance(row, dict)
        for item in [normalize_tpex(row)]
        if item
    ]


def ranking(
    rows: list[dict[str, Any]],
    field: str,
    descending: bool,
    limit: int = 50,
) -> list[dict[str, Any]]:
    valid = [r for r in rows if r.get(field) is not None]
    valid.sort(key=lambda r: r[field], reverse=descending)

    output = []
    for rank, row in enumerate(valid[:limit], start=1):
        value = row[field]
        output.append({
            "rank": rank,
            "market": row["market"],
            "code": row["code"],
            "name": row["name"],
            "net_shares": value,
            "net_lots": round(value / 1000, 3),
        })
    return output


def build_analysis() -> dict[str, Any]:
    now = datetime.now(TAIPEI)
    twse = load_json(latest_json(RAW_ROOT / "twse"))
    tpex = load_json(latest_json(RAW_ROOT / "tpex"))

    twse_rows = extract_twse(twse)
    tpex_rows = extract_tpex(tpex)
    rows = twse_rows + tpex_rows

    data_dates = [
        value
        for value in [
            twse.get("official_data_date") if twse else None,
            tpex.get("data_date") if tpex else None,
        ]
        if isinstance(value, str)
    ]

    coverage_ok = len(twse_rows) > 0 and len(tpex_rows) > 0

    notes = []
    if not twse_rows:
        notes.append("上市法人明細未取得")
    if not tpex_rows:
        notes.append("上櫃法人明細未取得或欄位未匹配")
    if not rows:
        notes.append("法人排行維持待更新")

    return {
        "schema_version": "2.6",
        "generated_at": now.isoformat(),
        "run_date": now.date().isoformat(),
        "data_date": max(data_dates) if data_dates else None,
        "status": "ok" if coverage_ok else ("partial" if rows else "pending"),
        "units": {
            "net_shares": "股",
            "net_lots": "張，1張=1000股",
        },
        "coverage": {
            "parsed_rows": len(rows),
            "twse_rows": len(twse_rows),
            "tpex_rows": len(tpex_rows),
            "full_market_coverage": coverage_ok,
        },
        "rankings": {
            "foreign_buy_top50": ranking(rows, "foreign_net_shares", True),
            "foreign_sell_top50": ranking(rows, "foreign_net_shares", False),
            "investment_trust_buy_top50": ranking(
                rows, "investment_trust_net_shares", True
            ),
            "investment_trust_sell_top50": ranking(
                rows, "investment_trust_net_shares", False
            ),
            "dealer_buy_top50": ranking(rows, "dealer_net_shares", True),
            "dealer_sell_top50": ranking(rows, "dealer_net_shares", False),
        },
        "notes": notes,
    }


def save(payload: dict[str, Any]) -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_ROOT / f"{payload['run_date']}.json"
    latest = OUTPUT_ROOT / "latest.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    output.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return output


def main() -> int:
    setup_logging()
    try:
        path = save(build_analysis())
        print(path.as_posix())
        return 0
    except Exception as exc:
        LOG.exception("Institutional analysis failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
