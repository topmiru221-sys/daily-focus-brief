from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "analysis"
RAW = ROOT / "data" / "raw"
OUT = DATA / "priority_history_universe.json"
TZ = ZoneInfo("Asia/Taipei")


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def add(store, code, reason, priority):
    code = str(code or "").strip()
    if len(code) != 4 or not code.isdigit():
        return
    item = store.setdefault(code, {"code": code, "priority": priority, "reasons": []})
    item["priority"] = min(item["priority"], priority)
    if reason not in item["reasons"]:
        item["reasons"].append(reason)


def num(value):
    try: return float(str(value).replace(",", "").replace("+", ""))
    except (TypeError, ValueError): return None


def main() -> int:
    pool = {}
    research = load(DATA / "research" / "latest.json")
    for key, priority in (("research_pool", 1), ("watch_pool", 2), ("avoid_pool", 4)):
        for row in research.get(key, []): add(pool, row.get("code"), key, priority)

    themes = load(DATA / "theme_intelligence" / "latest.json")
    hot_sector_ids = {s.get("id") for theme in themes.get("themes", [])[:6] for s in theme.get("sectors", [])}
    sectors = load(DATA / "sectors" / "latest.json")
    for row in sectors.get("rankings", []):
        priority = 1 if row.get("id") in hot_sector_ids or (row.get("rank") or 99) <= 5 else 3
        for code in row.get("members", []): add(pool, code, f"sector:{row.get('name')}", priority)
        for rep in row.get("representatives", []): add(pool, rep.get("code"), f"leader:{row.get('name')}", 1)

    inst = load(DATA / "institutional" / "latest.json")
    for key in ("foreign_buy_top50", "investment_trust_buy_top50"):
        for row in inst.get("rankings", {}).get(key, [])[:30]: add(pool, row.get("code"), key, 2)

    for folder, key, ck, closek, changek in (("twse", "stock_prices", "Code", "ClosingPrice", "Change"), ("tpex", "daily_close_quotes", "SecuritiesCompanyCode", "Close", "Change")):
        files = sorted((RAW / folder).glob("*.json"))
        if not files: continue
        ranked = []
        for row in load(files[-1]).get("datasets", {}).get(key, []):
            close, change = num(row.get(closek)), num(row.get(changek))
            previous = close - change if close is not None and change is not None else None
            if previous and previous > 0: ranked.append(((change / previous) * 100, row.get(ck)))
        for pct, code in sorted(ranked, reverse=True)[:100]: add(pool, code, f"daily_strength:{pct:.2f}%", 2)

    rows = sorted(pool.values(), key=lambda x: (x["priority"], x["code"]))
    payload = {"schema_version": "5.4.40-priority-120d", "generated_at": datetime.now(TZ).isoformat(), "target_records": 120, "count": len(rows), "stocks": rows}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"priority_codes": len(rows), "target_records": 120}, ensure_ascii=False))
    return 0


if __name__ == "__main__": raise SystemExit(main())
