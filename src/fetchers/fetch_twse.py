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
OUTPUT_DIR = Path("data/raw/twse")
LOG = logging.getLogger("fetch_twse")

ENDPOINTS = {
    "market_summary": "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK",
    "institutional_trading": "https://openapi.twse.com.tw/v1/fund/BFI82U",
    "stock_prices": "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def fetch_json(url: str, *, attempts: int = 3, timeout: int = 30) -> Any:
    headers = {
        "User-Agent": "daily-focus-brief/2.1",
        "Accept": "application/json",
    }

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if payload in (None, [], {}):
                raise ValueError("TWSE returned an empty payload")
            return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            LOG.warning("Fetch failed (%s/%s): %s", attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))

    raise RuntimeError(
        f"Unable to fetch TWSE data after {attempts} attempts: {last_error}"
    )


def build_snapshot() -> dict[str, Any]:
    now = datetime.now(TAIPEI)
    datasets: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for name, url in ENDPOINTS.items():
        try:
            datasets[name] = fetch_json(url)
            LOG.info("Fetched %s (%s records)", name, len(datasets[name]))
        except Exception as exc:
            errors[name] = str(exc)
            LOG.exception("Failed to fetch %s", name)

    if not datasets:
        raise RuntimeError(
            "All TWSE datasets failed; refusing to write an empty snapshot"
        )

    return {
        "schema_version": "2.1",
        "source": "Taiwan Stock Exchange OpenAPI",
        "generated_at": now.isoformat(),
        "data_date": now.date().isoformat(),
        "timezone": "Asia/Taipei",
        "status": "partial" if errors else "ok",
        "errors": errors,
        "datasets": datasets,
    }


def save_snapshot(snapshot: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{snapshot['data_date']}.json"
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
        LOG.info("TWSE snapshot written to %s", output_path)
        print(output_path.as_posix())
        return 0
    except Exception as exc:
        LOG.exception("TWSE fetch failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
