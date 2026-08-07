from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
T=ZoneInfo("Asia/Taipei"); S=Path("data/analysis/sectors/latest.json"); O=Path("data/analysis/capital_flow")
def load(p):
 try:return json.loads(p.read_text(encoding="utf-8"))
 except:return {}
def clamp(v,a,b):return max(a,min(b,v))
def main():
 now=datetime.now(T); src=load(S); rows=[]
 for s in src.get("rankings",[]):
  avg=float(s.get("average_change_pct") or 0); br=float(s.get("advance_ratio_pct") or 0); m20=float(s.get("above_20ma_ratio_pct") or 0); m60=float(s.get("above_60ma_ratio_pct") or 0); inst=float(s.get("institutional_net_shares_top50_scope") or 0)
  score=clamp(50+avg*5+(br-50)*.25+(m20-50)*.12+(m60-50)*.08+clamp(inst/2_000_000*10,-20,20),0,100)
  state="強勁流入" if score>=75 else "溫和流入" if score>=60 else "中性" if score>=45 else "資金轉弱" if score>=30 else "明顯流出"
  rows.append({"sector_id":s.get("id"),"sector_name":s.get("name"),"flow_score":round(score,1),"flow_state":state,"leaders":(s.get("representatives") or [])[:5],"data_quality":{"available_count":s.get("available_count"),"member_count":s.get("member_count")}})
 rows.sort(key=lambda x:x["flow_score"],reverse=True)
 for i,r in enumerate(rows,1):r["rank"]=i
 p={"schema_version":"4.1-alpha","generated_at":now.isoformat(),"data_date":src.get("run_date"),"status":"ok" if rows else "pending","inflow":rows[:5],"outflow":list(reversed(rows[-5:])),"rankings":rows,"methodology":{"note":"Alpha：族群漲幅、廣度、均線廣度與前50法人範圍加權。"}}
 O.mkdir(parents=True,exist_ok=True); txt=json.dumps(p,ensure_ascii=False,indent=2); (O/"latest.json").write_text(txt,encoding="utf-8"); (O/f"{now.date().isoformat()}.json").write_text(txt,encoding="utf-8")
if __name__=="__main__":main()
