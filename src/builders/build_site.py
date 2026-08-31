from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
TZ=ZoneInfo("Asia/Taipei"); OUT=Path("public/data")
SOURCES={"market":Path("data/analysis/market/latest.json"),"institutional":Path("data/analysis/institutional/latest.json"),"sectors":Path("data/analysis/sectors/latest.json"),"capital_flow":Path("data/analysis/capital_flow/latest.json"),"research":Path("data/analysis/research/latest.json"),"flow_persistence":Path("data/analysis/flow_persistence/latest.json"),"playbook":Path("data/analysis/playbook/latest.json"),"decision":Path("data/analysis/decision/latest.json"),"sector_center":Path("data/analysis/sector_center/latest.json"),"theme_intelligence":Path("data/analysis/theme_intelligence/latest.json"),"margin":Path("data/analysis/baseline/margin.json"),"securities_lending":Path("data/analysis/baseline/securities_lending.json"),"putcall":Path("data/analysis/baseline/putcall.json"),"vix":Path("data/analysis/baseline/vix.json"),"etf":Path("data/analysis/baseline/etf.json"),"warrant":Path("data/analysis/baseline/warrant.json"),"breadth":Path("data/analysis/breadth/latest.json"),"history":Path("data/analysis/history/latest.json")}
CORE=["market","institutional","sectors","capital_flow","research","flow_persistence","playbook","decision","sector_center","theme_intelligence"]
def read(p):
    try:
        v=json.loads(p.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {"status":"pending"}
    except Exception as e:return {"status":"pending","error":str(e),"source":str(p)}
def mdate(p):return p.get("data_date") or p.get("official_data_date") or p.get("run_date")
def main():
    OUT.mkdir(parents=True,exist_ok=True); payloads={k:read(v) for k,v in SOURCES.items()}; dates={}
    for n,p in payloads.items():
        dates[n]=mdate(p); (OUT/f"{n}.json").write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding="utf-8")
    core_dates=sorted({dates[k] for k in CORE if isinstance(dates.get(k),str)}); latest=max(core_dates) if core_dates else None; common=min(core_dates) if core_dates else None
    allowed={"ok","partial"}; blockers=[]
    for k in CORE:
        st=payloads[k].get("status","pending")
        if st not in allowed:blockers.append(f"{k}: status={st}")
        if not dates.get(k):blockers.append(f"{k}: missing data_date")
    if len(core_dates)>1:blockers.append("core module data dates are mixed")
    fresh={k:("missing" if not d else "unknown" if not latest else "fresh" if d==latest else "lagging") for k,d in dates.items()}
    lag=[k for k,v in fresh.items() if v=="lagging"]; miss=[k for k,v in fresh.items() if v=="missing"]; partial=[k for k,v in payloads.items() if v.get("status")=="partial"]
    meta={"schema_version":"5.4.41","generated_at":datetime.now(TZ).isoformat(),"latest_available_data_date":latest,"latest_common_data_date":common,"module_dates":dates,"module_freshness":fresh,"freshness_summary":{"fresh":sum(v=="fresh" for v in fresh.values()),"lagging":len(lag),"missing":len(miss),"lagging_modules":lag,"missing_modules":miss,"partial_modules":partial},"date_consistency":"ok" if len(core_dates)<=1 else "mixed","modules":{k:v.get("status","pending") for k,v in payloads.items()},"publish_ready":not blockers,"publication_blockers":blockers,"warning":None if not blockers else "發布守門檢查未通過；請先確認 publication_blockers。","integrity_note":"Fresh/lagging 以最新核心交易資料日為基準，不以週末或假日的日曆日期誤判資料過期。"}
    (OUT/"meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8");return 0
if __name__=="__main__":raise SystemExit(main())
