from __future__ import annotations

import json
import logging
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

TAIPEI = ZoneInfo("Asia/Taipei")
CONFIG_PATH = Path("config/sectors.json")
OUTPUT_ROOT = Path("data/history/prices")
LOG = logging.getLogger("fetch_history")

TWSE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
TPEX_URL = (
    "https://www.tpex.org.tw/web/stock/aftertrading/"
    "daily_trading_info/st43_result.php"
)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def request_json(
    url: str,
    *,
    params: dict[str, str],
    attempts: int = 3,
    timeout: int = 45,
) -> Any:
    headers = {
        "User-Agent": "daily-focus-brief/3.1",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.twse.com.tw/",
    }

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            LOG.warning(
                "Request failed %s/%s: %s",
                attempt,
                attempts,
                exc,
            )
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))

    raise RuntimeError(str(last_error))


def month_starts(month_count: int = 6) -> list[date]:
    today = datetime.now(TAIPEI).date()
    year, month = today.year, today.month
    output = []

    for _ in range(month_count):
        output.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year -= 1
            month = 12

    return sorted(output)


def number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").replace("+", "").strip()
    if text in {"", "--", "---", "除權", "除息", "除權息"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def roc_date_to_iso(value: Any) -> str | None:
    parts = re.findall(r"\d+", str(value or ""))
    if len(parts) < 3:
        return None
    try:
        return date(
            int(parts[0]) + 1911,
            int(parts[1]),
            int(parts[2]),
        ).isoformat()
    except ValueError:
        return None


def parse_twse(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("stat") != "OK":
        return []

    rows = payload.get("data", [])
    result = []

    for row in rows:
        if not isinstance(row, list) or len(row) < 9:
            continue

        trade_date = roc_date_to_iso(row[0])
        close = number(row[6])
        if not trade_date or close is None:
            continue

        result.append({
            "date": trade_date,
            "volume": number(row[1]),
            "trade_value": number(row[2]),
            "open": number(row[3]),
            "high": number(row[4]),
            "low": number(row[5]),
            "close": close,
            "change": number(row[7]),
            "transactions": number(row[8]),
        })

    return result


def parse_tpex(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    rows = (
        payload.get("aaData")
        or payload.get("data")
        or payload.get("tables")
        or []
    )

    if isinstance(rows, dict):
        rows = rows.get("data", [])

    result = []

    for row in rows:
        if isinstance(row, dict):
            trade_date = (
                roc_date_to_iso(
                    row.get("Date")
                    or row.get("日期")
                    or row.get("TradeDate")
                )
            )
            close = number(
                row.get("Close")
                or row.get("收盤價")
                or row.get("ClosingPrice")
            )
            if trade_date and close is not None:
                result.append({
                    "date": trade_date,
                    "volume": number(
                        row.get("Volume") or row.get("成交股數")
                    ),
                    "trade_value": number(
                        row.get("Amount") or row.get("成交金額")
                    ),
                    "open": number(
                        row.get("Open") or row.get("開盤價")
                    ),
                    "high": number(
                        row.get("High") or row.get("最高價")
                    ),
                    "low": number(
                        row.get("Low") or row.get("最低價")
                    ),
                    "close": close,
                    "change": number(
                        row.get("Change") or row.get("漲跌")
                    ),
                    "transactions": number(
                        row.get("Transactions") or row.get("成交筆數")
                    ),
                })
            continue

        if not isinstance(row, list) or len(row) < 7:
            continue

        trade_date = roc_date_to_iso(row[0])
        close = number(row[6] if len(row) > 6 else None)
        if not trade_date or close is None:
            continue

        result.append({
            "date": trade_date,
            "volume": number(row[1] if len(row) > 1 else None),
            "trade_value": number(row[2] if len(row) > 2 else None),
            "open": number(row[3] if len(row) > 3 else None),
            "high": number(row[4] if len(row) > 4 else None),
            "low": number(row[5] if len(row) > 5 else None),
            "close": close,
            "change": number(row[7] if len(row) > 7 else None),
            "transactions": number(row[8] if len(row) > 8 else None),
        })

    return result


def fetch_twse(code: str, months: list[date]) -> list[dict[str, Any]]:
    rows = []
    for month in months:
        payload = request_json(
            TWSE_URL,
            params={
                "response": "json",
                "date": month.strftime("%Y%m%d"),
                "stockNo": code,
            },
        )
        rows.extend(parse_twse(payload))
        time.sleep(0.35)
    return rows


def fetch_tpex(code: str, months: list[date]) -> list[dict[str, Any]]:
    rows = []
    for month in months:
        roc_year = month.year - 1911
        payload = request_json(
            TPEX_URL,
            params={
                "l": "zh-tw",
                "d": f"{roc_year}/{month.month:02d}",
                "stkno": code,
            },
        )
        rows.extend(parse_tpex(payload))
        time.sleep(0.35)
    return rows


def unique_codes() -> list[str]:
    config = load_json(CONFIG_PATH)
    return sorted({
        str(code)
        for sector in config.get("sectors", [])
        for code in sector.get("members", [])
    })


def merge_rows(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {
        str(row.get("date")): row
        for row in existing + new
        if row.get("date") and row.get("close") is not None
    }
    return [merged[key] for key in sorted(merged)]


def load_existing(code: str) -> list[dict[str, Any]]:
    path = OUTPUT_ROOT / f"{code}.json"
    if not path.exists():
        return []
    try:
        payload = load_json(path)
        rows = payload.get("prices", [])
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def save(code: str, market: str, rows: list[dict[str, Any]]) -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_ROOT / f"{code}.json"
    payload = {
        "schema_version": "3.1",
        "code": code,
        "market": market,
        "updated_at": datetime.now(TAIPEI).isoformat(),
        "record_count": len(rows),
        "first_date": rows[0]["date"] if rows else None,
        "last_date": rows[-1]["date"] if rows else None,
        "prices": rows,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def main() -> int:
    setup_logging()
    months = month_starts(6)
    failures = []

    for index, code in enumerate(unique_codes(), start=1):
        LOG.info("Fetching %s (%s)", code, index)
        rows = []
        market = "unknown"

        try:
            rows = fetch_twse(code, months)
            if rows:
                market = "TWSE"
            else:
                rows = fetch_tpex(code, months)
                if rows:
                    market = "TPEx"

            if not rows:
                failures.append({
                    "code": code,
                    "error": "No official historical rows returned",
                })
                continue

            merged = merge_rows(load_existing(code), rows)
            save(code, market, merged)

        except Exception as exc:
            LOG.exception("Failed %s", code)
            failures.append({
                "code": code,
                "error": str(exc),
            })

    summary = {
        "generated_at": datetime.now(TAIPEI).isoformat(),
        "requested_codes": len(unique_codes()),
        "failed_codes": failures,
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "_status.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
