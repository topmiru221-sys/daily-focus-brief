from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Asia/Taipei")
SRC=Path("data/analysis/sector_center/latest.json")
OUT=Path("data/analysis/theme_intelligence")

def load(path):
    try:
        v=json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v,dict) else {}
    except Exception:
        return {}

def avg(vals):
    vals=[float(v) for v in vals if isinstance(v,(int,float))]
    return round(sum(vals)/len(vals),2) if vals else None

def score_row(sectors):
    flow=avg([s.get("flow_score") for s in sectors])
    persistence=avg([s.get("persistence_ratio_pct") for s in sectors])
    breadth=avg([s.get("advance_ratio_pct") for s in sectors])
    ma60=avg([s.get("above_60ma_ratio_pct") for s in sectors])
    decision=avg([s.get("average_decision_score") for s in sectors])
    parts=[]
    if flow is not None: parts.append(max(0,min(100,flow))*0.30)
    if persistence is not None: parts.append(max(0,min(100,persistence))*0.25)
    if breadth is not None: parts.append(max(0,min(100,breadth))*0.20)
    if ma60 is not None: parts.append(max(0,min(100,ma60))*0.15)
    if decision is not None: parts.append(max(0,min(100,decision))*0.10)
    strength=round(sum(parts)/(0.30+0.25+0.20+0.15+0.10),1) if len(parts)==5 else None
    if strength is None: state="資料不足"
    elif strength>=70: state="強勢主題"
    elif strength>=55: state="轉強／擴散"
    elif strength>=40: state="中性觀察"
    else: state="弱勢／退潮"
    leaders=[]
    for s in sectors:
        l=s.get("leader") or {}
        if l.get("code"):
            leaders.append({"sector_id":s.get("id"),"sector_name":s.get("name"),"code":l.get("code"),"name":l.get("name"),"decision_score":l.get("decision_score"),"risk_pct":l.get("risk_pct"),"rr1":l.get("rr1")})
    leaders.sort(key=lambda x:(x.get("decision_score") is not None,x.get("decision_score") or -1),reverse=True)
    return {"strength_score":strength,"state":state,"flow_score":flow,"persistence_ratio_pct":persistence,"advance_ratio_pct":breadth,"above_60ma_ratio_pct":ma60,"average_decision_score":decision,"sector_count":len(sectors),"leaders":leaders[:5]}

def main():
    now=datetime.now(TZ); src=load(SRC); sectors=src.get("sectors") or []
    mega_map={}; theme_map={}
    for s in sectors:
        tax=s.get("taxonomy") or {}
        for name in tax.get("mega_theme") or []: mega_map.setdefault(name,[]).append(s)
        for name in tax.get("theme") or []: theme_map.setdefault(name,[]).append(s)
    mega=[]; themes=[]
    for name,rows in mega_map.items():
        x={"name":name,**score_row(rows),"sectors":[{"id":s.get("id"),"name":s.get("name"),"today_rank":s.get("today_rank"),"flow_score":s.get("flow_score"),"persistence_ratio_pct":s.get("persistence_ratio_pct")} for s in rows]}
        mega.append(x)
    for name,rows in theme_map.items():
        x={"name":name,**score_row(rows),"mega_themes":sorted({m for s in rows for m in ((s.get("taxonomy") or {}).get("mega_theme") or [])}),"sectors":[{"id":s.get("id"),"name":s.get("name"),"today_rank":s.get("today_rank"),"flow_score":s.get("flow_score"),"persistence_ratio_pct":s.get("persistence_ratio_pct")} for s in rows]}
        themes.append(x)
    key=lambda x:(x.get("strength_score") is not None,x.get("strength_score") or -1)
    mega.sort(key=key,reverse=True); themes.sort(key=key,reverse=True)
    for i,x in enumerate(mega,1): x["rank"]=i
    for i,x in enumerate(themes,1): x["rank"]=i
    payload={"schema_version":"5.4.33-theme-intelligence","generated_at":now.isoformat(),"data_date":src.get("data_date"),"status":"ok" if sectors else "pending","mega_theme_count":len(mega),"theme_count":len(themes),"mega_themes":mega,"themes":themes,"methodology":{"strength_score":"Flow 30% + Persistence 25% + Advance Breadth 20% + Above MA60 15% + Decision 10%. 僅在五項皆有資料時產生分數。","note":"Theme Intelligence 為研究排序與輪動觀察，不構成買賣建議。"}}
    OUT.mkdir(parents=True,exist_ok=True)
    text=json.dumps(payload,ensure_ascii=False,indent=2)
    (OUT/"latest.json").write_text(text,encoding="utf-8")
    (OUT/f"{now.date().isoformat()}.json").write_text(text,encoding="utf-8")
    return 0
if __name__=="__main__": raise SystemExit(main())
