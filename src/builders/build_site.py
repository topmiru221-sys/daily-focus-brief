from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TAIPEI=ZoneInfo("Asia/Taipei")
OUT=Path("public/data")
SOURCES={
 "market":Path("data/analysis/market/latest.json"),
 "institutional":Path("data/analysis/institutional/latest.json"),
 "sectors":Path("data/analysis/sectors/latest.json"),
 "capital_flow":Path("data/analysis/capital_flow/latest.json"),
 "research":Path("data/analysis/research/latest.json"),
 "flow_persistence":Path("data/analysis/flow_persistence/latest.json"),
 "playbook":Path("data/analysis/playbook/latest.json"),
 "decision":Path("data/analysis/decision/latest.json"),
}
def read(path):
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value,dict) else {"status":"pending"}
    except Exception as exc:
        return {"status":"pending","error":str(exc),"source":str(path)}
def module_date(payload):
    return payload.get("data_date") or payload.get("official_data_date") or payload.get("run_date")
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    payloads={name:read(path) for name,path in SOURCES.items()}
    dates={}
    for name,payload in payloads.items():
        dates[name]=module_date(payload)
        (OUT/f"{name}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    valid=sorted({value for value in dates.values() if isinstance(value,str)})
    meta={
      "schema_version":"5.0-alpha",
      "generated_at":datetime.now(TAIPEI).isoformat(),
      "latest_available_data_date":max(valid) if valid else None,
      "latest_common_data_date":min(valid) if valid else None,
      "module_dates":dates,
      "date_consistency":"ok" if len(valid)<=1 else "mixed",
      "modules":{name:payload.get("status","pending") for name,payload in payloads.items()},
      "warning":None if len(valid)<=1 else "各模組資料日期不一致，請依個別日期判讀。"
    }
    (OUT/"meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
