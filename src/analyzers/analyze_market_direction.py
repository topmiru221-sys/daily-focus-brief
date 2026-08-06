from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
OUTPUT_ROOT = Path("data/analysis/market")
LOG = logging.getLogger("analyze_market_direction")


def load(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def latest_raw(source: str) -> dict[str, Any] | None:
    files = sorted(Path(f"data/raw/{source}").glob("*.json"))
    return load(files[-1]) if files else None


def num(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def latest_twse_row(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    rows = payload.get("datasets", {}).get("market_summary", [])
    if not isinstance(rows, list) or not rows:
        return None
    valid = [r for r in rows if isinstance(r, dict) and r.get("Date")]
    return max(valid, key=lambda r: str(r.get("Date"))) if valid else None


def extract_put_call(payload: dict[str, Any] | None) -> float | None:
    if not payload:
        return None
    rows = payload.get("datasets", {}).get("put_call_ratio", [])
    if not isinstance(rows, list) or not rows:
        return None

    for row in rows[:10]:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            key_text = str(key).lower().replace(" ", "")
            if "putcallratio" in key_text or "買賣權未平倉量比率" in key_text:
                parsed = num(value)
                if parsed is not None:
                    return parsed
    return None


def build() -> dict[str, Any]:
    now = datetime.now(TAIPEI)
    twse = latest_raw("twse")
    taifex = latest_raw("taifex")
    institutional = load(Path("data/analysis/institutional/latest.json"))

    signals: list[dict[str, Any]] = []

    twse_row = latest_twse_row(twse)
    if twse_row:
        change = num(twse_row.get("Change"))
        if change is not None:
            signals.append({
                "name": "加權指數漲跌點",
                "value": change,
                "unit": "點",
                "direction": "positive" if change > 0 else (
                    "negative" if change < 0 else "neutral"
                ),
                "score": 1 if change > 0 else (-1 if change < 0 else 0),
            })

    pcr = extract_put_call(taifex)
    if pcr is not None:
        signals.append({
            "name": "Put/Call Ratio",
            "value": pcr,
            "unit": "%",
            "direction": (
                "positive" if pcr >= 100 else
                "negative" if pcr < 80 else
                "neutral"
            ),
            "score": 1 if pcr >= 100 else (-1 if pcr < 80 else 0),
        })

    coverage = (
        institutional.get("coverage", {})
        if isinstance(institutional, dict)
        else {}
    )
    full_market = bool(coverage.get("full_market_coverage"))

    valid_scores = [s["score"] for s in signals]
    total_score = sum(valid_scores)

    if len(valid_scores) < 2:
        verdict = "待更新"
        confidence = "insufficient"
    elif total_score >= 2:
        verdict = "偏多"
        confidence = "preliminary"
    elif total_score <= -2:
        verdict = "偏空"
        confidence = "preliminary"
    else:
        verdict = "中性"
        confidence = "preliminary"

    warnings = []
    if not full_market:
        warnings.append("法人資料尚未涵蓋上市＋上櫃全市場")
    if len(valid_scores) < 2:
        warnings.append("可核對訊號不足，不產生市場健康分數")

    return {
        "schema_version": "2.6",
        "generated_at": now.isoformat(),
        "run_date": now.date().isoformat(),
        "status": "ok" if len(valid_scores) >= 2 else "partial",
        "verdict": verdict,
        "confidence": confidence,
        "score": total_score if len(valid_scores) >= 2 else None,
        "score_range": [-2, 2],
        "signals": signals,
        "warnings": warnings,
        "methodology": {
            "minimum_signals": 2,
            "rule": "僅使用可核對官方資料；不足時顯示待更新",
        },
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
    logging.basicConfig(level=logging.INFO)
    try:
        path = save(build())
        print(path.as_posix())
        return 0
    except Exception as exc:
        LOG.exception("Market direction analysis failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
