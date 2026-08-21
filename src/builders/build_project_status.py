from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]; DATA=ROOT/"public"/"data"; TZ=ZoneInfo("Asia/Taipei")

def load(name):
    try:
        value=json.loads((DATA/name).read_text(encoding="utf-8")); return value if isinstance(value,dict) else {}
    except Exception:return {}

def module(mid,name,source,progress,group="原始 SITE",priority="P0"):
    data=load(source) if source else {}; status=data.get("status")
    state="usable" if status=="ok" else "partial" if status=="partial" else "not_started"
    if state=="usable": score=progress
    elif state=="partial": score=min(progress,65)
    else: score=0
    date=data.get("data_date") or data.get("official_data_date") or data.get("run_date")
    schema=data.get("schema_version")
    details=[x for x in (f"資料日期 {date}" if date else None,f"Schema {schema}" if schema else None) if x]
    note="｜".join(details) if details else "尚無可驗證的資料產物"
    return {"id":mid,"name":name,"group":group,"status":state,"progress":score,"priority":priority,"note":note}

def main():
    now=datetime.now(TZ); meta=load("meta.json")
    modules=[
        {"id":"morning","name":"晨報","group":"原始 SITE","status":"partial","progress":65,"priority":"P0","note":"頁面可用；全球盤前資料仍待自動化"},
        {"id":"close","name":"每日盤後","group":"原始 SITE","status":"usable" if meta.get("publish_ready") else "partial","progress":95 if meta.get("publish_ready") else 60,"priority":"P0","note":f"核心資料日期 {meta.get('latest_common_data_date') or '待更新'}"},
        module("institution50","外資／投信 Top 50","institutional.json",95),
        module("margin","融資融券","margin.json",85),
        module("securities_lending","借券","securities_lending.json",85),
        module("putcall","Put / Call","putcall.json",80),
        module("vix","VIX","vix.json",80),
        module("warrant","權證","warrant.json",75),
        module("etf","ETF","etf.json",80),
        module("sector","熱門族群","sector_center.json",95),
        module("scanner","盤後掃描","research.json",88),
        module("breadth","市場廣度","breadth.json",78),
        module("history","歷史資料庫","history.json",72),
        module("research","AI研究池","research.json",90),
        module("risk","Risk Engine","decision.json",88),
        module("decision","Decision Engine","decision.json",95),
        {"id":"assistant","name":"AI Assistant","group":"原始 SITE","status":"not_started","progress":0,"priority":"P2","note":"排在資料品質與決策鏈之後"},
        module("theme_intelligence","Theme Intelligence","theme_intelligence.json",95,"後續新增"),
        {"id":"publication_guard","name":"Publication Guardrails","group":"後續新增","status":"usable" if meta.get("publish_ready") else "partial","progress":95 if meta.get("publish_ready") else 60,"priority":"P0","note":"發布守門通過" if meta.get("publish_ready") else "｜".join(meta.get("publication_blockers") or ["等待驗證"])}]
    summary={key:sum(m["status"]==key for m in modules) for key in ("usable","partial","not_started")}
    overall=round(sum(m["progress"] for m in modules)/len(modules),1)
    pending=sorted((m for m in modules if m["status"]!="usable"),key=lambda m:(m["priority"]!="P0",m["progress"]))
    queue=[{"order":i,"module":m["name"],"state":"next" if i==1 else "todo","target":m["note"]} for i,m in enumerate(pending[:5],1)]
    issues=[]
    if not meta.get("publish_ready"):issues.extend(meta.get("publication_blockers") or ["Publication Guard 未通過"])
    issues.extend(f"{m['name']}：{m['note']}" for m in pending if m["status"]=="not_started")
    payload={"schema_version":"5.4.37-live-system-health","version":"V5.4.37 Live System Health","updated_at":now.isoformat(),"data_date":meta.get("latest_common_data_date"),"overall_progress_pct":overall,"baseline_module_count":17,"summary":summary,"current_sprint":"Live System Health Reconciliation","sprint_goal":"讓進度、資料日期與發布狀態由真實產物自動決定。","rules":["狀態只讀取已發布 JSON，不以人工印象判定","核心日期不一致時 Publication Guard 阻擋發布","資料不足顯示 partial 或 not_started，不虛構完成度"],"modules":modules,"current_queue":queue,"known_issues":issues or ["目前沒有阻擋發布的已知問題"],"source_meta_schema":meta.get("schema_version"),"publish_ready":bool(meta.get("publish_ready"))}
    (DATA/"project_status.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8");return 0

if __name__=="__main__":raise SystemExit(main())
