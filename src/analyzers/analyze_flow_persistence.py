from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
SECTOR_DIR = Path("data/analysis/sectors")
OUTPUT_DIR = Path("data/analysis/flow_persistence")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def recent_sector_files(limit: int = 5) -> list[Path]:
    files = sorted(
        path for path in SECTOR_DIR.glob("*.json")
        if path.name != "latest.json"
    )
    return files[-limit:]


def state_label(days: int, positive_days: int, slope: float, latest: float) -> str:
    if days < 2:
        return "資料累積中"
    if positive_days == days and slope > 3:
        return "連續流入且加速"
    if positive_days >= max(2, days - 1) and slope >= 0:
        return "持續流入"
    if latest >= 60 and slope < -3:
        return "仍強但流速下降"
    if latest >= 50 and slope > 3:
        return "首次轉強"
    if latest < 45 and slope < 0:
        return "持續轉弱"
    return "震盪輪動"


def flow_score(row: dict) -> float:
    avg = float(row.get("average_change_pct") or 0)
    breadth = float(row.get("advance_ratio_pct") or 0)
    ma20 = float(row.get("above_20ma_ratio_pct") or 0)
    ma60 = float(row.get("above_60ma_ratio_pct") or 0)
    inst = float(row.get("institutional_net_shares_top50_scope") or 0)
    available = float(row.get("available_count") or 0)
    members = float(row.get("member_count") or 0)
    coverage = available / members if members else 0

    institutional_component = max(-18, min(18, inst / 2_000_000 * 8))
    raw = (
        50
        + avg * 4.2
        + (breadth - 50) * 0.18
        + (ma20 - 50) * 0.08
        + (ma60 - 50) * 0.06
        + institutional_component
    )
    confidence_adjusted = 50 + (raw - 50) * max(0.35, coverage)
    return round(max(0, min(100, confidence_adjusted)), 2)


def main() -> int:
    now = datetime.now(TAIPEI)
    files = recent_sector_files(5)
    snapshots = []

    for path in files:
        payload = load_json(path)
        data_date = payload.get("run_date") or path.stem
        rows = {
            str(row.get("id")): row
            for row in payload.get("rankings", [])
            if isinstance(row, dict) and row.get("id")
        }
        snapshots.append((data_date, rows))

    all_ids = sorted({
        sector_id
        for _, rows in snapshots
        for sector_id in rows
    })

    rankings = []
    for sector_id in all_ids:
        series = []
        names = []
        leaders_by_day = []

        for data_date, rows in snapshots:
            row = rows.get(sector_id)
            if not row:
                continue
            score = flow_score(row)
            series.append({
                "date": data_date,
                "flow_score": score,
                "rank": row.get("rank"),
                "average_change_pct": row.get("average_change_pct"),
                "advance_ratio_pct": row.get("advance_ratio_pct"),
            })
            names.append(row.get("name"))
            leaders_by_day.append({
                "date": data_date,
                "leaders": [
                    {
                        "code": stock.get("code"),
                        "name": stock.get("name"),
                        "change_pct": stock.get("change_pct"),
                    }
                    for stock in (row.get("representatives") or [])[:5]
                ],
            })

        if not series:
            continue

        scores = [item["flow_score"] for item in series]
        latest = scores[-1]
        slope = latest - scores[0] if len(scores) >= 2 else 0
        positive_days = sum(score >= 55 for score in scores)
        average_score = mean(scores)

        leader_counts = defaultdict(int)
        latest_leaders = leaders_by_day[-1]["leaders"] if leaders_by_day else []
        for day in leaders_by_day:
            for leader in day["leaders"][:3]:
                code = str(leader.get("code") or "")
                if code:
                    leader_counts[code] += 1

        current_leader = latest_leaders[0] if latest_leaders else None
        prior_leader = None
        if len(leaders_by_day) >= 2 and leaders_by_day[-2]["leaders"]:
            prior_leader = leaders_by_day[-2]["leaders"][0]

        leadership_change = bool(
            current_leader and prior_leader
            and current_leader.get("code") != prior_leader.get("code")
        )

        rankings.append({
            "sector_id": sector_id,
            "sector_name": next((name for name in reversed(names) if name), sector_id),
            "effective_days": len(series),
            "latest_score": latest,
            "average_score": round(average_score, 2),
            "score_change": round(slope, 2),
            "positive_days": positive_days,
            "persistence_ratio_pct": round(positive_days / len(series) * 100, 2),
            "state": state_label(len(series), positive_days, slope, latest),
            "series": series,
            "current_leader": current_leader,
            "prior_leader": prior_leader,
            "leadership_change": leadership_change,
            "leader_frequency": [
                {"code": code, "days_in_top3": days}
                for code, days in sorted(
                    leader_counts.items(),
                    key=lambda item: (-item[1], item[0])
                )[:5]
            ],
            "leaders_by_day": leaders_by_day,
        })

    rankings.sort(
        key=lambda row: (
            row["average_score"],
            row["latest_score"],
            row["persistence_ratio_pct"],
        ),
        reverse=True,
    )

    for rank, row in enumerate(rankings, start=1):
        row["rank"] = rank

    payload = {
        "schema_version": "4.3",
        "generated_at": now.isoformat(),
        "data_date": snapshots[-1][0] if snapshots else None,
        "status": "ok" if rankings else "pending",
        "effective_trading_days": len(snapshots),
        "requested_trading_days": 5,
        "history_dates": [date for date, _ in snapshots],
        "rankings": rankings,
        "persistent_inflow": [
            row for row in rankings
            if row["state"] in {"連續流入且加速", "持續流入"}
        ][:5],
        "new_strength": [
            row for row in rankings
            if row["state"] == "首次轉強"
        ][:5],
        "slowing": [
            row for row in rankings
            if row["state"] in {"仍強但流速下降", "持續轉弱"}
        ][:5],
        "leadership_changes": [
            row for row in rankings
            if row["leadership_change"]
        ][:8],
        "methodology": {
            "flow_score": "族群漲幅、廣度、20/60MA廣度、法人前50範圍與資料覆蓋率",
            "persistence": "實際存在的最近5個交易日中，flow_score >= 55 的比例",
            "limitation": "法人仍為前50排行範圍；有效歷史不足5日時照實標示",
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    (OUTPUT_DIR / f"{now.date().isoformat()}.json").write_text(text, encoding="utf-8")
    (OUTPUT_DIR / "latest.json").write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
