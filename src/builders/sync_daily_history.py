from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
HISTORY = ROOT / "data" / "history" / "prices"
TZ = ZoneInfo("Asia/Taipei")


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def number(value):
    try:
        return float(str(value).replace(",", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def rows_from(path: Path, market: str):
    payload = load(path)
    if market == "TWSE":
        rows = payload.get("datasets", {}).get("stock_prices", [])
        fields = ("Code", "Name", "OpeningPrice", "HighestPrice", "LowestPrice", "ClosingPrice", "TradeVolume", "TradeValue", "Transaction")
    else:
        rows = payload.get("datasets", {}).get("daily_close_quotes", [])
        fields = ("SecuritiesCompanyCode", "CompanyName", "Open", "High", "Low", "Close", "TradingShares", "TransactionAmount", "TransactionNumber")
    day = payload.get("data_date") or path.stem
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get(fields[0]) or "").strip()
        close = number(row.get(fields[5]))
        if len(code) != 4 or not code.isdigit() or close is None or close <= 0:
            continue
        yield code, row.get(fields[1]) or code, {
            "date": day,
            "open": number(row.get(fields[2])), "high": number(row.get(fields[3])),
            "low": number(row.get(fields[4])), "close": close,
            "volume": number(row.get(fields[6])), "trade_value": number(row.get(fields[7])),
            "transactions": number(row.get(fields[8])),
        }


def main() -> int:
    HISTORY.mkdir(parents=True, exist_ok=True)
    collected = {}
    for folder, market in (("twse", "TWSE"), ("tpex", "TPEx")):
        for path in sorted((RAW / folder).glob("*.json")):
            for code, name, row in rows_from(path, market):
                item = collected.setdefault(code, {"name": name, "market": market, "rows": {}})
                item["rows"][row["date"]] = row
    for code, item in collected.items():
        path = HISTORY / f"{code}.json"
        old = load(path)
        merged = {str(row.get("date")): row for row in old.get("prices", []) if row.get("date") and number(row.get("close")) is not None}
        merged.update(item["rows"])
        prices = [merged[key] for key in sorted(merged)]
        payload = {
            "schema_version": "5.4.39-daily-history-sync", "code": code,
            "name": item["name"], "market": item["market"],
            "updated_at": datetime.now(TZ).isoformat(), "record_count": len(prices),
            "first_date": prices[0]["date"] if prices else None,
            "last_date": prices[-1]["date"] if prices else None, "prices": prices,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    status = {"schema_version": "5.4.39-daily-history-sync", "generated_at": datetime.now(TZ).isoformat(), "synced_codes": len(collected)}
    (HISTORY / "_daily_sync_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
