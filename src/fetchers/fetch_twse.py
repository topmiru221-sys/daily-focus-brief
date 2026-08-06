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
OUTPUT_DIR = Path("data/raw/twse")
LOG = logging.getLogger("fetch_twse")

OPENAPI_ENDPOINTS = {
    "market_summary": "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK",
    "stock_prices": "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
    "margin_balance": "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN",
    "advance_decline": "https://openapi.twse.com.tw/v1/opendata/twtazu_od",
}

LEGACY_BASE = "https://www.twse.com.tw/rwd/zh/fund"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def request_json(
    url: str,
    *,
    params: dict[str, str] | None = None,
    attempts: int = 3,
    timeout: int = 45,
) -> Any:
    headers = {
        "User-Agent": "daily-focus-brief/2.5",
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
            payload = response.json()
            if payload in (None, [], {}):
                raise ValueError("TWSE returned an empty payload")
            return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            LOG.warning(
                "Fetch failed (%s/%s) %s: %s",
                attempt,
                attempts,
                url,
                exc,
            )
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))

    raise RuntimeError(
        f"Unable to fetch TWSE data after {attempts} attempts: {last_error}"
    )


def roc_to_yyyymmdd(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 7:
        return None

    try:
        year = int(digits[:3]) + 1911
        month = int(digits[3:5])
        day = int(digits[5:7])
        return date(year, month, day).strftime("%Y%m%d")
    except ValueError:
        return None


def latest_market_date(market_summary: Any) -> str | None:
    if not isinstance(market_summary, list):
        return None

    valid_dates = [
        converted
        for row in market_summary
        if isinstance(row, dict)
        for converted in [roc_to_yyyymmdd(row.get("Date"))]
        if converted
    ]
    return max(valid_dates) if valid_dates else None


def fetch_legacy_report(
    report: str,
    data_date: str,
    *,
    select_type: str | None = None,
) -> dict[str, Any]:
    params = {
        "response": "json",
        "date": data_date,
        "dayDate": data_date,
        "type": "day",
    }
    if select_type:
        params["selectType"] = select_type

    payload = request_json(f"{LEGACY_BASE}/{report}", params=params)

    if not isinstance(payload, dict):
        raise ValueError(f"{report} payload is not an object")

    if payload.get("stat") != "OK":
        raise ValueError(
            f"{report} official status is not OK: {payload.get('stat')}"
        )

    if report == "T86" and not payload.get("data"):
        raise ValueError("T86 contains no institutional detail rows")

    return payload


def build_snapshot() -> dict[str, Any]:
    now = datetime.now(TAIPEI)
    datasets: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for name, url in OPENAPI_ENDPOINTS.items():
        try:
            datasets[name] = request_json(url)
            LOG.info("Fetched %s", name)
        except Exception as exc:
            errors[name] = str(exc)
            LOG.exception("Failed to fetch %s", name)

    official_date = latest_market_date(datasets.get("market_summary"))
    if official_date:
        legacy_reports = {
            "institutional_summary": ("BFI82U", None),
            "institutional_detail": ("T86", "ALLBUT0999"),
        }
        for name, (report, select_type) in legacy_reports.items():
            try:
                datasets[name] = fetch_legacy_report(
                    report,
                    official_date,
                    select_type=select_type,
                )
                LOG.info("Fetched %s for %s", name, official_date)
            except Exception as exc:
                errors[name] = str(exc)
                LOG.exception("Failed to fetch %s", name)
    else:
        errors["institutional_reports"] = (
            "Unable to determine latest official TWSE market date"
        )

    if not datasets:
        raise RuntimeError(
            "All TWSE datasets failed; refusing to write an empty snapshot"
        )

    return {
        "schema_version": "2.5",
        "source": "Taiwan Stock Exchange official APIs",
        "generated_at": now.isoformat(),
        "run_date": now.date().isoformat(),
        "official_data_date": (
            datetime.strptime(official_date, "%Y%m%d").date().isoformat()
            if official_date
            else None
        ),
        "timezone": "Asia/Taipei",
        "status": "partial" if errors else "ok",
        "errors": errors,
        "datasets": datasets,
    }


def save_snapshot(snapshot: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{snapshot['run_date']}.json"
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
