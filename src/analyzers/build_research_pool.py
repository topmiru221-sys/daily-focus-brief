from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
T=ZoneInfo("Asia/Taipei"); S=Path("data/analysis/sectors/latest.json"); F=Path("data/analysis/capital_flow/latest.json"); O=Path("data/analysis/research")
def load(p):
 try:return json.loads(p.read_text(encoding="utf-8"))
 except:return {}
def main():
 now=datetime.now(T); s=load(S); f=load(F); fm={x.get("sector_id"):x for x in f.get("rankings",[])}; c={}
 for sec in s.get("rankings",[]):
  fs=float(fm.get(sec.get("id"),{}).get("flow_score") or 0)
  for st in (sec.get("representatives") or [])[:5]:
   code=str(st.get("code") or ""); ch=float(st.get("change_pct") or 0)
   if not code:continue
   score=round(min(100,max(0,fs*.65+min(max(ch,0),10)*3.5)),1); x=c.setdefault(code,{"code":code,"name":st.get("name"),"market":st.get("market"),"score":0,"sectors":[],"reasons":[],"risk_flags":[]}); x["score"]=max(x["score"],score); x["sectors"].append(sec.get("name")); x["reasons"] += [f"{sec.get('name')} 資金分數 {fs:.1f}",f"當日漲跌幅 {ch:.2f}%"]
   if ch>=8:x["risk_flags"].append("當日漲幅偏大，追價風險提高")
 pool=sorted(c.values(),key=lambda x:x["score"],reverse=True); p={"schema_version":"4.1-alpha","generated_at":now.isoformat(),"data_date":f.get("data_date") or s.get("run_date"),"status":"ok" if pool else "pending","research_pool":[x for x in pool if x["score"]>=70][:10],"watch_pool":[x for x in pool if 55<=x["score"]<70][:10],"avoid_pool":[x for x in pool if x["risk_flags"] and x["score"]<70][:10],"disclaimer":"僅供縮小研究範圍，不構成買賣建議。"}
 O.mkdir(parents=True,exist_ok=True); txt=json.dumps(p,ensure_ascii=False,indent=2); (O/"latest.json").write_text(txt,encoding="utf-8"); (O/f"{now.date().isoformat()}.json").write_text(txt,encoding="utf-8")
if __name__=="__main__":main()
