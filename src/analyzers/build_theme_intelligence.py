from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
TZ=ZoneInfo("Asia/Taipei"); SRC=Path("data/analysis/sector_center/latest.json"); OUT=Path("data/analysis/theme_intelligence")
def load(p):
    try:
        v=json.loads(p.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:return {}
def avg(vs):
    vs=[float(v) for v in vs if isinstance(v,(int,float))]; return round(sum(vs)/len(vs),2) if vs else None
def previous_files(today):
    files=[]
    if OUT.exists():
        for p in OUT.glob("????-??-??.json"):
            if p.name!=f"{today}.json": files.append(p)
    return sorted(files,reverse=True)
def history_map(files,kind):
    out=[]
    for p in files[:5]:
        d=load(p)
        rows=d.get(kind) or []
        out.append((d.get("data_date") or p.stem,{x.get("name"):x for x in rows if x.get("name")}))
    return out
def rotation(now_score, hist_scores):
    if now_score is None:return {"rotation_state":"資料不足","score_change_1d":None,"score_change_5d":None,"confirmation_days":0}
    valid=[x for x in hist_scores if x is not None]
    d1=round(now_score-valid[0],1) if valid else None; d5=round(now_score-valid[-1],1) if valid else None
    conf=1
    for x in valid:
        if x>=55: conf+=1
        else: break
    prev=valid[0] if valid else None
    if now_score>=70 and (d1 is None or d1>=3): state="加速強勢"
    elif now_score>=55 and prev is not None and prev<55: state="新轉強"
    elif now_score>=55 and conf>=2: state="持續強勢"
    elif prev is not None and prev>=55 and now_score<55 and now_score>=40: state="降溫"
    elif prev is not None and prev>=40 and now_score<40: state="退潮"
    elif now_score>=55 and d1 is not None and d1<=-8: state="假突破風險"
    elif now_score>=40: state="中性觀察"
    else: state="弱勢"
    return {"rotation_state":state,"score_change_1d":d1,"score_change_5d":d5,"confirmation_days":conf if now_score>=55 else 0}
def score_row(sectors):
    flow=avg([s.get("flow_score") for s in sectors]); per=avg([s.get("persistence_ratio_pct") for s in sectors]); br=avg([s.get("advance_ratio_pct") for s in sectors]); ma=avg([s.get("above_60ma_ratio_pct") for s in sectors]); dec=avg([s.get("average_decision_score") for s in sectors])
    strength=round(flow*.30+per*.25+br*.20+ma*.15+dec*.10,1) if None not in (flow,per,br,ma,dec) else None
    state="資料不足" if strength is None else "強勢主題" if strength>=70 else "轉強／擴散" if strength>=55 else "中性觀察" if strength>=40 else "弱勢／退潮"
    leaders=[]
    for s in sectors:
        l=s.get("leader") or {}
        if l.get("code"):leaders.append({"sector_id":s.get("id"),"sector_name":s.get("name"),"code":l.get("code"),"name":l.get("name"),"decision_score":l.get("decision_score"),"risk_pct":l.get("risk_pct"),"rr1":l.get("rr1")})
    leaders.sort(key=lambda x:(x.get("decision_score") is not None,x.get("decision_score") or -1),reverse=True)
    return {"strength_score":strength,"state":state,"flow_score":flow,"persistence_ratio_pct":per,"advance_ratio_pct":br,"above_60ma_ratio_pct":ma,"average_decision_score":dec,"sector_count":len(sectors),"leaders":leaders[:5]}
def main():
    now=datetime.now(TZ); today=now.date().isoformat(); src=load(SRC); sectors=src.get("sectors") or []; prev=previous_files(today); mega_hist=history_map(prev,"mega_themes"); theme_hist=history_map(prev,"themes")
    maps={"mega_themes":{},"themes":{}}
    for s in sectors:
        tax=s.get("taxonomy") or {}
        for n in tax.get("mega_theme") or []:maps["mega_themes"].setdefault(n,[]).append(s)
        for n in tax.get("theme") or []:maps["themes"].setdefault(n,[]).append(s)
    payload={"schema_version":"5.4.34-theme-rotation","generated_at":now.isoformat(),"data_date":src.get("data_date"),"status":"ok" if sectors else "pending"}
    for kind,hist in (("mega_themes",mega_hist),("themes",theme_hist)):
        rows=[]
        for name,ss in maps[kind].items():
            base=score_row(ss); hs=[m.get(name,{}).get("strength_score") for _,m in hist]
            x={"name":name,**base,**rotation(base.get("strength_score"),hs),"history":[{"date":d,"strength_score":m.get(name,{}).get("strength_score")} for d,m in hist]}
            if kind=="themes":x["mega_themes"]=sorted({m for s in ss for m in ((s.get("taxonomy") or {}).get("mega_theme") or [])})
            x["sectors"]=[{"id":s.get("id"),"name":s.get("name"),"today_rank":s.get("today_rank"),"flow_score":s.get("flow_score"),"persistence_ratio_pct":s.get("persistence_ratio_pct")} for s in ss]; rows.append(x)
        rows.sort(key=lambda x:(x.get("strength_score") is not None,x.get("strength_score") or -1),reverse=True)
        for i,x in enumerate(rows,1):x["rank"]=i
        payload[kind]=rows
    payload["mega_theme_count"]=len(payload.get("mega_themes",[])); payload["theme_count"]=len(payload.get("themes",[])); payload["history_days_available"]=len(prev[:5]); payload["methodology"]={"strength_score":"Flow 30% + Persistence 25% + Advance Breadth 20% + Above MA60 15% + Decision 10%.","rotation":"以目前分數與最近最多5個交易日歷史比較；歷史不足時保留當日判讀，不虛構變化。"}
    OUT.mkdir(parents=True,exist_ok=True); text=json.dumps(payload,ensure_ascii=False,indent=2); (OUT/"latest.json").write_text(text,encoding="utf-8"); (OUT/f"{today}.json").write_text(text,encoding="utf-8"); return 0
if __name__=="__main__":raise SystemExit(main())
