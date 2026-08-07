from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
T=ZoneInfo("Asia/Taipei"); P=Path("public/data"); S={"market":Path("data/analysis/market/latest.json"),"institutional":Path("data/analysis/institutional/latest.json"),"sectors":Path("data/analysis/sectors/latest.json"),"capital_flow":Path("data/analysis/capital_flow/latest.json"),"research":Path("data/analysis/research/latest.json")}
def load(p):
 try:return json.loads(p.read_text(encoding="utf-8"))
 except:return {"status":"pending"}
def main():
 P.mkdir(parents=True,exist_ok=True); ps={}; dates={}
 for n,p in S.items():
  x=load(p); ps[n]=x; dates[n]=x.get("data_date") or x.get("official_data_date"); (P/f"{n}.json").write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
 valid=[x for x in dates.values() if isinstance(x,str)]; meta={"schema_version":"4.1-alpha","generated_at":datetime.now(T).isoformat(),"latest_common_data_date":min(valid) if valid else None,"latest_available_data_date":max(valid) if valid else None,"module_dates":dates,"date_consistency":"ok" if len(set(valid))<=1 else "mixed","modules":{k:v.get("status","pending") for k,v in ps.items()},"warning":None if len(set(valid))<=1 else "各模組資料日期不一致，請分別判讀。"}; (P/"meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
