from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
FLOW = Path("data/analysis/flow_persistence/latest.json")
SECTORS = Path("data/analysis/sectors/latest.json")
MARKET = Path("data/analysis/market/latest.json")
OUTPUT = Path("data/analysis/playbook")


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def main() -> int:
    now = datetime.now(TAIPEI)
    flow = load(FLOW)
    sectors = load(SECTORS)
    market = load(MARKET)

    rankings = flow.get("rankings", [])
    strongest = rankings[:3]
    weakest = sorted(
        rankings,
        key=lambda row: (row.get("latest_score") or 0)
    )[:3]

    changes = []
    for row in flow.get("leadership_changes", [])[:3]:
        current = row.get("current_leader") or {}
        prior = row.get("prior_leader") or {}
        changes.append(
            f"{row.get('sector_name')} 龍頭由 "
            f"{prior.get('name') or prior.get('code') or '待確認'} "
            f"轉為 {current.get('name') or current.get('code') or '待確認'}"
        )

    for row in flow.get("new_strength", [])[:3]:
        changes.append(
            f"{row.get('sector_name')} 資金首次轉強，"
            f"近期期末分數 {row.get('latest_score')}"
        )

    for row in flow.get("slowing", [])[:2]:
        changes.append(
            f"{row.get('sector_name')} 資金流速下降，"
            f"分數變化 {row.get('score_change')}"
        )

    if not changes:
        changes.append("歷史資料仍在累積，暫無足夠變化訊號。")

    focus_sectors = [
        {
            "name": row.get("sector_name"),
            "state": row.get("state"),
            "latest_score": row.get("latest_score"),
            "persistence_ratio_pct": row.get("persistence_ratio_pct"),
            "leader": row.get("current_leader"),
        }
        for row in strongest
    ]

    risk_sectors = [
        {
            "name": row.get("sector_name"),
            "state": row.get("state"),
            "latest_score": row.get("latest_score"),
            "score_change": row.get("score_change"),
        }
        for row in weakest
    ]

    market_verdict = market.get("verdict") or "待更新"
    if focus_sectors:
        headline = (
            f"市場方向：{market_verdict}；"
            f"資金目前優先聚焦 "
            + "、".join(item["name"] for item in focus_sectors[:3])
            + "。"
        )
    else:
        headline = f"市場方向：{market_verdict}；資金資料仍在累積。"

    payload = {
        "schema_version": "4.3",
        "generated_at": now.isoformat(),
        "data_date": flow.get("data_date") or sectors.get("run_date"),
        "status": "ok",
        "headline": headline,
        "what_changed_today": changes[:5],
        "focus_sectors": focus_sectors,
        "risk_sectors": risk_sectors,
        "rotation_summary": {
            "from": [item["name"] for item in risk_sectors],
            "to": [item["name"] for item in focus_sectors],
            "note": "此為相對資金強弱推論，不代表資金可被精確追蹤為封閉流量。",
        },
        "tomorrow_questions": [
            f"{item['name']} 的資金持續度能否維持？"
            for item in focus_sectors[:3]
        ],
        "disclaimer": "市場劇本用於整理可驗證訊號，不構成買賣建議。",
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    (OUTPUT / f"{now.date().isoformat()}.json").write_text(text, encoding="utf-8")
    (OUTPUT / "latest.json").write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
