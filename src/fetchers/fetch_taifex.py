from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

TAIPEI = ZoneInfo("Asia/Taipei")
OUTPUT_DIR = Path("data/raw/taifex")
LOG = logging.getLogger("fetch_taifex")

BASE_URL = "https://openapi.taifex.com.tw/v1"

ENDPOINTS = {
    "futures_daily_market": f"{BASE_URL}/DailyMarketReportFut",
    "options_daily_market": f"{BASE_URL}/DailyMarketReportOpt",
    "put_call_ratio": f"{BASE_URL}/PutCallRatio",
    "institutional_general": (
        f"{BASE_URL}/MarketDataOfMajorInstitutionalTradersGeneralBytheDate"
    ),
    "institutional_futures": (
        f"{BASE_URL}/"
        "MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate"
    ),
    "institutional_options": (
        f"{BASE_URL}/"
        "MarketDataOfMajorInstitutionalTradersDetailsOfOptionsContractsBytheDate"
    ),
    "institutional_calls_puts": (
        f"{BASE_URL}/"
        "MarketDataOfMajorInstitutionalTradersDetailsOfCallsAndPutsBytheDate"
    ),
    "large_trader_futures_oi": f"{BASE_URL}/OpenInterestOfLargeTradersFutures",
    "large_trader_options_oi": f"{BASE_URL}/OpenInterestOfLargeTradersOptions",
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def fetch_json(url: str, *, attempts: int = 3, timeout: int = 45) -> Any:
    headers = {
        "User-Agent": "daily-focus-brief/2.3",
        "Accept": "application/json",
    }

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if payload in (None, [], {}):
                raise ValueError("TAIFEX returned an empty payload")
            return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            LOG.warning("Fetch failed (%s/%s): %s", attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))

    raise RuntimeError(
        f"Unable to fetch TAIFEX data after {attempts} attempts: {last_error}"
    )


def detect_data_dates(payload: Any) -> list[str]:
    dates: set[str] = set()

    if not isinstance(payload, list):
        return []

    for row in payload[:200]:
        if not isinstance(row, dict):
            continue
        for key in ("Date", "date", "TradeDate", "TradingDate"):
            value = row.get(key)
            if value:
                dates.add(str(value))
    return sorted(dates)


def build_snapshot() -> dict[str, Any]:
    now = datetime.now(TAIPEI)
    datasets: dict[str, Any] = {}
    dataset_dates: dict[str, list[str]] = {}
    errors: dict[str, str] = {}

    for name, url in ENDPOINTS.items():
        try:
            payload = fetch_json(url)
            datasets[name] = payload
            dataset_dates[name] = detect_data_dates(payload)
            record_count = len(payload) if hasattr(payload, "__len__") else "unknown"
            LOG.info("Fetched %s (%s records)", name, record_count)
        except Exception as exc:
            errors[name] = str(exc)
            LOG.exception("Failed to fetch %s", name)

    if not datasets:
        raise RuntimeError(
            "All TAIFEX datasets failed; refusing to write an empty snapshot"
        )

    return {
        "schema_version": "2.3",
        "source": "Taiwan Futures Exchange OpenAPI",
        "generated_at": now.isoformat(),
        "snapshot_date": now.date().isoformat(),
        "timezone": "Asia/Taipei",
        "status": "partial" if errors else "ok",
        "errors": errors,
        "dataset_dates": dataset_dates,
        "datasets": datasets,
    }


def save_snapshot(snapshot: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{snapshot['snapshot_date']}.json"
    temp_path = output_path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(output_path)
    return output_path


def main() -> int:
    setup_logging()
    try:
        snapshot = build_snapshot()
        output_path = save_snapshot(snapshot)
        LOG.info("TAIFEX snapshot written to %s", output_path)
        print(output_path.as_posix())
        return 0
    except Exception as exc:
        LOG.exception("TAIFEX fetch failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
