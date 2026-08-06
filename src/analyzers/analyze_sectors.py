from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
CONFIG_PATH = Path("config/sectors.json")
RAW_ROOT = Path("data/raw")
OUTPUT_ROOT = Path("data/analysis/sectors")
INSTITUTIONAL_PATH = Path("data/analysis/institutional/latest.json")
LOG = logging.getLogger("analyze_sectors")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def latest_json(directory: Path) -> Path | None:
    files = sorted(path for path in directory.glob("*.json") if path.name != "latest.json")
    return files[-1] if files else None


def number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").replace("%", "").strip()
    if text in {"", "--", "---", "N/A", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def first(row: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    normalized = {str(k).lower().replace(" ", "").replace("_", ""): v for k, v in row.items()}
    for key in keys:
        target = key.lower().replace(" ", "").replace("_", "")
        if target in normalized:
            return normalized[target]
    return None


def pct_change(close: float | None, change: float | None) -> float | None:
    if close is None or change is None:
        return None
    previous = close - change
    if previous == 0:
        return None
    return change / previous * 100


def extract_twse(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not payload:
        return result
    rows = payload.get("datasets", {}).get("stock_prices", [])
    if not isinstance(rows, list):
        return result

    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(first(row, ["Code", "證券代號", "股票代號"]) or "").strip()
        if not code:
            continue
        close = number(first(row, ["ClosingPrice", "Close", "收盤價"]))
        change = number(first(row, ["Change", "漲跌價差"]))
        result[code] = {
            "market": "TWSE",
            "code": code,
            "name": str(first(row, ["Name", "證券名稱", "股票名稱"]) or "").strip(),
            "close": close,
            "change": change,
            "change_pct": pct_change(close, change),
            "trade_value": number(first(row, ["TradeValue", "成交金額"])),
            "volume": number(first(row, ["TradeVolume", "成交股數"])),
        }
    return result


def extract_tpex(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not payload:
        return result
    rows = payload.get("datasets", {}).get("daily_close_quotes", [])
    if not isinstance(rows, list):
        return result

    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(first(row, [
            "SecuritiesCompanyCode", "SecurityCode", "Code", "股票代號", "代號"
        ]) or "").strip()
        if not code:
            continue
        close = number(first(row, [
            "Close", "ClosePrice", "ClosingPrice", "收盤價"
        ]))
        change = number(first(row, [
            "Change", "ChangePrice", "漲跌", "漲跌價差"
        ]))
        change_pct = number(first(row, [
            "ChangePercent", "ChangeRate", "漲跌幅"
        ]))
        if change_pct is None:
            change_pct = pct_change(close, change)

        result[code] = {
            "market": "TPEx",
            "code": code,
            "name": str(first(row, [
                "CompanyName", "SecurityName", "Name", "股票名稱", "名稱"
            ]) or "").strip(),
            "close": close,
            "change": change,
            "change_pct": change_pct,
            "trade_value": number(first(row, [
                "TransactionAmount", "TradeValue", "成交金額"
            ])),
            "volume": number(first(row, [
                "TransactionVolume", "TradeVolume", "成交股數"
            ])),
        }
    return result


def institutional_map(payload: dict[str, Any] | None) -> dict[str, float]:
    output: dict[str, float] = {}
    if not payload:
        return output

    rankings = payload.get("rankings", {})
    if not isinstance(rankings, dict):
        return output

    for key in (
        "foreign_buy_top50", "foreign_sell_top50",
        "investment_trust_buy_top50", "investment_trust_sell_top50",
        "dealer_buy_top50", "dealer_sell_top50",
    ):
        rows = rankings.get(key, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("code") or "").strip()
            value = number(row.get("net_shares"))
            if code and value is not None:
                output[code] = output.get(code, 0.0) + value
    return output


def classify(avg_change: float | None, breadth: float | None, institutional: float) -> str:
    if avg_change is None or breadth is None:
        return "資料不足"
    if avg_change >= 2 and breadth >= 70 and institutional > 0:
        return "資金＋趨勢共振"
    if avg_change >= 1 and breadth >= 55:
        return "族群擴散中"
    if avg_change >= 1:
        return "個股帶動／短線集中"
    return "未達強勢門檻"


def build() -> dict[str, Any]:
    now = datetime.now(TAIPEI)
    config = load_json(CONFIG_PATH) or {}
    twse = load_json(latest_json(RAW_ROOT / "twse")) if latest_json(RAW_ROOT / "twse") else None
    tpex = load_json(latest_json(RAW_ROOT / "tpex")) if latest_json(RAW_ROOT / "tpex") else None
    institutional = load_json(INSTITUTIONAL_PATH)

    stocks = extract_twse(twse)
    stocks.update(extract_tpex(tpex))
    inst = institutional_map(institutional)

    strong_threshold = number(config.get("methodology", {}).get("strong_stock_threshold_pct")) or 3.0
    output = []

    for sector in config.get("sectors", []):
        members = [str(code) for code in sector.get("members", [])]
        available = [stocks[code] for code in members if code in stocks and stocks[code].get("change_pct") is not None]
        changes = [row["change_pct"] for row in available]
        avg_change = sum(changes) / len(changes) if changes else None
        rising = sum(1 for value in changes if value > 0)
        breadth = rising / len(changes) * 100 if changes else None
        strong = sum(1 for value in changes if value >= strong_threshold)
        inst_net = sum(inst.get(code, 0.0) for code in members)

        representatives = sorted(
            available,
            key=lambda row: (
                row.get("change_pct") if row.get("change_pct") is not None else -999,
                row.get("trade_value") if row.get("trade_value") is not None else 0,
            ),
            reverse=True,
        )[:5]

        output.append({
            "id": sector.get("id"),
            "name": sector.get("name"),
            "member_count": len(members),
            "available_count": len(available),
            "average_change_pct": round(avg_change, 3) if avg_change is not None else None,
            "advance_ratio_pct": round(breadth, 2) if breadth is not None else None,
            "strong_stock_count": strong,
            "institutional_net_shares_top50_scope": inst_net,
            "above_60ma_ratio_pct": None,
            "above_60ma_status": "歷史資料不足",
            "classification": classify(avg_change, breadth, inst_net),
            "representatives": [
                {
                    "market": row["market"],
                    "code": row["code"],
                    "name": row["name"],
                    "change_pct": round(row["change_pct"], 3),
                    "trade_value": row.get("trade_value"),
                }
                for row in representatives
            ],
            "members": members,
        })

    output.sort(
        key=lambda row: (
            row["average_change_pct"] is not None,
            row["average_change_pct"] if row["average_change_pct"] is not None else -999,
            row["advance_ratio_pct"] if row["advance_ratio_pct"] is not None else -999,
        ),
        reverse=True,
    )

    for rank, row in enumerate(output, start=1):
        row["rank"] = rank

    return {
        "schema_version": "3.0-alpha1",
        "generated_at": now.isoformat(),
        "run_date": now.date().isoformat(),
        "status": "ok" if any(row["available_count"] >= 3 for row in output) else "partial",
        "methodology": config.get("methodology", {}),
        "sector_count": len(output),
        "rankings": output,
        "warnings": [
            "法人淨買超目前僅以進入前50排行的股票加總，不代表全族群完整法人總額",
            "60日均線比例將於累積足夠歷史行情後啟用",
        ],
    }


def save(payload: dict[str, Any]) -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    dated = OUTPUT_ROOT / f"{payload['run_date']}.json"
    latest = OUTPUT_ROOT / "latest.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    dated.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return dated


def main() -> int:
    setup_logging()
    try:
        path = save(build())
        print(path.as_posix())
        return 0
    except Exception as exc:
        LOG.exception("Sector analysis failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
