from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(path: str) -> dict:
    target = ROOT / path
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AssertionError(f"{path}: cannot read JSON ({exc})") from exc
    assert isinstance(value, dict), f"{path}: root must be an object"
    return value

def main() -> int:
    meta=load("public/data/meta.json"); themes=load("public/data/theme_intelligence.json"); sectors=load("public/data/sector_center.json"); project=load("public/data/project_status.json"); decision=load("public/data/decision.json"); errors=[]
    if not meta.get("publish_ready"): errors.extend(meta.get("publication_blockers") or ["meta.publish_ready is false"])
    if themes.get("status")!="ok": errors.append(f"theme_intelligence status={themes.get('status')}")
    if not str(themes.get("schema_version","")).startswith("5.4.36"): errors.append("theme_intelligence schema is not V5.4.36")
    if themes.get("data_date")!=sectors.get("data_date"): errors.append("Theme Intelligence and Sector Center dates differ")
    if not str(project.get("schema_version","")).startswith("5.4.37"): errors.append("project_status schema is not V5.4.37")
    if project.get("data_date")!=meta.get("latest_common_data_date"): errors.append("Project Status and core data dates differ")
    if not str(decision.get("schema_version","")).startswith("5.4.38"): errors.append("Decision schema is not V5.4.38")
    if decision.get("decision_count",0)<decision.get("universe_count",0): errors.append("Decision cards do not cover the daily universe")
    if decision.get("universe_count",0)<1000: errors.append("Decision daily universe is unexpectedly small")
    sector_ids={row.get("id") for row in sectors.get("sectors") or []}; rows=themes.get("themes") or []
    if [row.get("rank") for row in rows]!=list(range(1,len(rows)+1)): errors.append("Theme ranks are not continuous")
    for row in rows:
        name=row.get("name") or "<unnamed>"
        if row.get("confidence_score") is None or not row.get("decision_posture"): errors.append(f"{name}: missing confidence/posture")
        missing=[item.get("id") for item in row.get("sectors") or [] if item.get("id") not in sector_ids]
        if missing: errors.append(f"{name}: unknown sector links {missing}")
    if errors:
        print("Market Close publication validation FAILED")
        for error in errors: print(f"- {error}")
        return 1
    print(f"Market Close publication validation OK: {themes.get('data_date')} / {len(rows)} themes")
    return 0

if __name__=="__main__": raise SystemExit(main())
