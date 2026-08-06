from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TAIPEI=ZoneInfo("Asia/Taipei")
PUBLIC_DATA=Path("public/data")
SOURCES={
 "market":Path("data/analysis/market/latest.json"),
 "institutional":Path("data/analysis/institutional/latest.json"),
 "sectors":Path("data/analysis/sectors/latest.json"),
}
def read_json(path):
    if not path.exists():
        return {"status":"pending","notes":[f"{path} not found"]}
    try:
        p=json.loads(path.read_text(encoding="utf-8"))
        return p if isinstance(p,dict) else {"status":"pending"}
    except json.JSONDecodeError:
        return {"status":"pending","notes":[f"{path} invalid json"]}
def main():
    PUBLIC_DATA.mkdir(parents=True,exist_ok=True)
    payloads={}
    for name,source in SOURCES.items():
        p=read_json(source);payloads[name]=p
        (PUBLIC_DATA/f"{name}.json").write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding="utf-8")
    dates=[p.get("data_date") or p.get("run_date") for p in payloads.values() if isinstance(p,dict)]
    dates=[x for x in dates if isinstance(x,str)]
    meta={"schema_version":"3.3-alpha","generated_at":datetime.now(TAIPEI).isoformat(),"data_date":max(dates) if dates else None,"modules":{k:v.get("status","pending") for k,v in payloads.items()}}
    (PUBLIC_DATA/"meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
