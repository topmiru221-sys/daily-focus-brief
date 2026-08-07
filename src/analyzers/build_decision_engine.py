from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
RESEARCH_PATH = Path("data/analysis/research/latest.json")
SECTOR_PATH = Path("data/analysis/sectors/latest.json")
FLOW_PATH = Path("data/analysis/flow_persistence/latest.json")
HISTORY_ROOT = Path("data/history/prices")
OUTPUT_ROOT = Path("data/analysis/decision")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def average(values):
    clean = [value for value in values if value is not None]
    return mean(clean) if clean else None


def pct(current, reference):
    if current is None or reference in (None, 0):
        return None
    return (current / reference - 1) * 100


def rr(entry, stop, target):
    if None in (entry, stop, target) or entry <= stop or target <= entry:
        return None
    return (target - entry) / (entry - stop)


def grade(score):
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    return "D"


def history_metrics(code: str) -> dict:
    payload = load_json(HISTORY_ROOT / f"{code}.json")
    rows = [
        row for row in payload.get("prices", [])
        if isinstance(row, dict) and num(row.get("close")) is not None
    ]
    if not rows:
        return {
            "status": "missing",
            "price_date": None,
            "record_count": 0,
        }

    closes = [num(row.get("close")) for row in rows]
    highs = [num(row.get("high")) for row in rows]
    lows = [num(row.get("low")) for row in rows]
    volumes = [num(row.get("volume")) for row in rows]
    latest = rows[-1]
    close = num(latest.get("close"))
    volume = num(latest.get("volume"))

    ma20 = average(closes[-20:]) if len(closes) >= 20 else None
    ma60 = average(closes[-60:]) if len(closes) >= 60 else None
    avg_volume20 = average(volumes[-20:]) if len(volumes) >= 20 else None

    low20 = min(value for value in lows[-20:] if value is not None) if len(lows) >= 20 else None
    low60 = min(value for value in lows[-60:] if value is not None) if len(lows) >= 60 else low20
    high20 = max(value for value in highs[-20:] if value is not None) if len(highs) >= 20 else None
    high60 = max(value for value in highs[-60:] if value is not None) if len(highs) >= 60 else high20

    support_candidates = [
        ("20日均線", ma20),
        ("近20日低點", low20),
        ("60日均線", ma60),
        ("近60日低點", low60),
    ]
    supports = sorted(
        [
            {"label": label, "price": round(value, 2), "distance_pct": round(pct(value, close), 2)}
            for label, value in support_candidates
            if value is not None and value < close
        ],
        key=lambda item: item["price"],
        reverse=True,
    )

    resistance_candidates = [
        ("近20日高點", high20),
        ("近60日高點", high60),
    ]
    resistances = sorted(
        [
            {"label": label, "price": round(value, 2), "upside_pct": round(pct(value, close), 2)}
            for label, value in resistance_candidates
            if value is not None and value > close
        ],
        key=lambda item: item["price"],
    )

    stop = None
    if supports:
        stop = supports[0]["price"] * 0.985
    elif low20 is not None:
        stop = low20 * 0.985

    target1 = resistances[0]["price"] if resistances else None
    target2 = resistances[1]["price"] if len(resistances) > 1 else None

    return {
        "status": "ok",
        "price_date": latest.get("date"),
        "record_count": len(rows),
        "close": round(close, 2),
        "ma20": round(ma20, 2) if ma20 is not None else None,
        "ma60": round(ma60, 2) if ma60 is not None else None,
        "distance_ma20_pct": round(pct(close, ma20), 2) if ma20 else None,
        "distance_ma60_pct": round(pct(close, ma60), 2) if ma60 else None,
        "volume": volume,
        "avg_volume20": round(avg_volume20, 2) if avg_volume20 is not None else None,
        "volume_ratio20": round(volume / avg_volume20, 2) if volume and avg_volume20 else None,
        "supports": supports[:3],
        "resistances": resistances[:3],
        "suggested_stop": round(stop, 2) if stop is not None else None,
        "target1": target1,
        "target2": target2,
        "risk_pct": round((close - stop) / close * 100, 2) if stop else None,
        "reward1_pct": round((target1 - close) / close * 100, 2) if target1 else None,
        "reward2_pct": round((target2 - close) / close * 100, 2) if target2 else None,
        "rr1": round(rr(close, stop, target1), 2) if rr(close, stop, target1) else None,
        "rr2": round(rr(close, stop, target2), 2) if rr(close, stop, target2) else None,
    }


def main() -> int:
    now = datetime.now(TAIPEI)
    research = load_json(RESEARCH_PATH)
    sectors = load_json(SECTOR_PATH)
    flow = load_json(FLOW_PATH)

    sector_by_name = {
        str(row.get("name")): row
        for row in sectors.get("rankings", [])
        if isinstance(row, dict)
    }
    flow_by_name = {
        str(row.get("sector_name")): row
        for row in flow.get("rankings", [])
        if isinstance(row, dict)
    }

    combined = []
    for pool_name, source_key in [
        ("research", "research_pool"),
        ("watch", "watch_pool"),
        ("avoid", "avoid_pool"),
    ]:
        for item in research.get(source_key, []):
            if not isinstance(item, dict):
                continue
            copy = dict(item)
            copy["source_pool"] = pool_name
            combined.append(copy)

    seen = set()
    decisions = []

    for item in combined:
        code = str(item.get("code") or "")
        if not code or code in seen:
            continue
        seen.add(code)

        technical = history_metrics(code)
        sector_names = [str(name) for name in item.get("sectors", [])]
        sector_rows = [sector_by_name[name] for name in sector_names if name in sector_by_name]
        flow_rows = [flow_by_name[name] for name in sector_names if name in flow_by_name]

        sector_score = average([
            num(row.get("average_change_pct")) * 8 + 50
            for row in sector_rows
            if num(row.get("average_change_pct")) is not None
        ])
        sector_score = max(0, min(100, sector_score)) if sector_score is not None else 50

        flow_score = average([
            num(row.get("average_score")) or num(row.get("latest_score"))
            for row in flow_rows
        ]) or 50

        institution_score = 50
        if sector_rows:
            inst_total = sum(num(row.get("institutional_net_shares_top50_scope")) or 0 for row in sector_rows)
            institution_score = max(0, min(100, 50 + inst_total / 2_000_000 * 5))

        technical_score = 50
        risk_score = 50
        risk_flags = list(item.get("risk_flags") or [])
        reasons = list(item.get("reasons") or [])

        if technical.get("status") == "ok":
            technical_score = 50
            d20 = technical.get("distance_ma20_pct")
            d60 = technical.get("distance_ma60_pct")
            vr = technical.get("volume_ratio20")

            if d20 is not None:
                technical_score += 12 if 0 <= d20 <= 8 else 5 if d20 > 8 else -12
                if d20 > 12:
                    risk_flags.append("距離20日均線過遠，回檔風險提高")
                reasons.append(f"距離20MA {d20:+.2f}%")
            if d60 is not None:
                technical_score += 12 if d60 >= 0 else -15
                reasons.append(f"距離60MA {d60:+.2f}%")
            if vr is not None:
                technical_score += 8 if 1.2 <= vr <= 2.5 else -5 if vr > 3 else 0
                reasons.append(f"成交量為20日均量 {vr:.2f} 倍")

            technical_score = max(0, min(100, technical_score))

            risk_pct_value = technical.get("risk_pct")
            rr1_value = technical.get("rr1")
            risk_score = 50
            if risk_pct_value is not None:
                risk_score += 20 if risk_pct_value <= 5 else 5 if risk_pct_value <= 8 else -20
            if rr1_value is not None:
                risk_score += 25 if rr1_value >= 2 else 8 if rr1_value >= 1.3 else -20
                if rr1_value < 1.3:
                    risk_flags.append("第一目標風險報酬比偏低")
            risk_score = max(0, min(100, risk_score))
        else:
            risk_flags.append("缺少歷史行情，技術與風險分數可信度不足")

        research_score = num(item.get("score")) or 50
        decision_score = (
            research_score * 0.22
            + sector_score * 0.20
            + flow_score * 0.18
            + institution_score * 0.15
            + technical_score * 0.15
            + risk_score * 0.10
        )

        confidence_components = [
            technical.get("status") == "ok",
            bool(sector_rows),
            bool(flow_rows),
            bool(item.get("reasons")),
        ]
        confidence = round(sum(confidence_components) / len(confidence_components) * 100, 1)

        if item.get("source_pool") == "avoid":
            decision_score = min(decision_score, 59)
        elif risk_flags and decision_score > 89:
            decision_score = 89

        decision_score = round(max(0, min(100, decision_score)), 1)

        decisions.append({
            "code": code,
            "name": item.get("name"),
            "market": item.get("market"),
            "source_pool": item.get("source_pool"),
            "sectors": sector_names,
            "decision_score": decision_score,
            "grade": grade(decision_score),
            "confidence_pct": confidence,
            "components": {
                "research": round(research_score, 1),
                "sector": round(sector_score, 1),
                "flow": round(flow_score, 1),
                "institution": round(institution_score, 1),
                "technical": round(technical_score, 1),
                "risk_quality": round(risk_score, 1),
            },
            "technical": technical,
            "reasons": list(dict.fromkeys(reasons))[:8],
            "risk_flags": list(dict.fromkeys(risk_flags))[:8],
            "conclusion": (
                "可進一步建立交易計畫"
                if decision_score >= 80 and not risk_flags
                else "條件佳，但需先處理風險旗標"
                if decision_score >= 75
                else "列入觀察，等待更佳位置"
                if decision_score >= 60
                else "目前不優先"
            ),
        })

    decisions.sort(key=lambda row: (row["decision_score"], row["confidence_pct"]), reverse=True)

    payload = {
        "schema_version": "5.0-alpha",
        "generated_at": now.isoformat(),
        "data_date": research.get("data_date"),
        "status": "ok" if decisions else "pending",
        "decision_count": len(decisions),
        "rankings": decisions,
        "research_pool": [row for row in decisions if row["decision_score"] >= 75][:10],
        "watch_pool": [row for row in decisions if 60 <= row["decision_score"] < 75][:10],
        "avoid_pool": [
            row for row in decisions
            if row["decision_score"] < 60 or len(row["risk_flags"]) >= 2
        ][:10],
        "methodology": {
            "weights": {
                "research": 0.22,
                "sector": 0.20,
                "flow": 0.18,
                "institution": 0.15,
                "technical": 0.15,
                "risk_quality": 0.10,
            },
            "support_resistance": "使用最近20/60日高低點與20/60MA形成第一版參考",
            "stop": "第一支撐下方1.5%的結構失效參考，不是固定投資建議",
            "warning": "歷史價格日期可能落後當日盤後資料，網站必須顯示price_date",
        },
        "disclaimer": "本模組用於建立研究與風險計畫，不構成任何買賣建議。",
    }

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    (OUTPUT_ROOT / f"{now.date().isoformat()}.json").write_text(text, encoding="utf-8")
    (OUTPUT_ROOT / "latest.json").write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
