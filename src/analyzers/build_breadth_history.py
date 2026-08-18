from __future__ import annotations
import json, re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Asia/Taipei")
OUT=Path("data/analysis")
OUT.mkdir(parents=True,exist_ok=True)

def latest_json(folder):
    fs=sorted([p for p in Path(folder).glob("20*.json") if p.name!="latest.json"])
    if not fs:return {}
    return json.loads(fs[-1].read_text(encoding="utf-8"))

def num(v):
    if v is None:return None
    s=str(v).replace(",","").replace("%","").strip()
    if s in ("","--","-"):return None
    try:return float(s)
    except:return None

def first(r,*ks):
    for k in ks:
        if k in r and r[k] not in (None,""):return r[k]
    return None

def build_breadth():
    twse=latest_json("data/raw/twse")
    rows=twse.get("datasets",{}).get("stock_prices",[])
    up=down=flat=valid=0
    limit_up=limit_down=0
    top_up=[]; top_down=[]
    for r in rows if isinstance(rows,list) else []:
        if not isinstance(r,dict): continue
        code=str(first(r,"Code","證券代號","股票代號") or "")
        if not re.fullmatch(r"\d{4}",code): continue
        name=str(first(r,"Name","證券名稱","股票名稱") or "")
        ch=num(first(r,"Change","漲跌價差","ChangePercent","漲跌百分比"))
        pct=num(first(r,"ChangePercent","漲跌百分比","漲跌幅"))
        if ch is None: continue
        valid+=1
        item={"code":code,"name":name,"change":ch,"change_pct":pct}
        if ch>0:
            up+=1; top_up.append(item)
        elif ch<0:
            down+=1; top_down.append(item)
        else: flat+=1
        if pct is not None and pct>=9.5: limit_up+=1
        if pct is not None and pct<=-9.5: limit_down+=1
    top_up.sort(key=lambda x:(x["change_pct"] if x["change_pct"] is not None else x["change"]),reverse=True)
    top_down.sort(key=lambda x:(x["change_pct"] if x["change_pct"] is not None else x["change"]))
    total=up+down+flat
    payload={
      "status":"ok" if valid else "pending",
      "data_date":twse.get("official_data_date"),
      "generated_at":datetime.now(TZ).isoformat(),
      "source":"TWSE STOCK_DAY_ALL",
      "summary":{
        "advance":up,"decline":down,"unchanged":flat,"total":total,
        "advance_ratio_pct":round(up/total*100,2) if total else None,
        "decline_ratio_pct":round(down/total*100,2) if total else None,
        "advance_decline_ratio":round(up/down,2) if down else None,
        "limit_up":limit_up if any(x.get("change_pct") is not None for x in top_up) else None,
        "limit_down":limit_down if any(x.get("change_pct") is not None for x in top_down) else None
      },
      "leaders":top_up[:10],"laggards":top_down[:10],
      "note":"漲停/跌停僅在來源含可辨識漲跌幅欄位時顯示；否則為 null。"
    }
    p=OUT/"breadth";p.mkdir(exist_ok=True)
    (p/"latest.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    if payload["data_date"]:
        (p/f'{payload["data_date"]}.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

def build_history():
    records=[]
    for p in sorted(Path("data/normalized").glob("20*.json")):
        try:
            n=json.loads(p.read_text(encoding="utf-8"))
        except: continue
        d=n.get("run_date") or p.stem
        tw=n.get("market",{}).get("twse",{})
        mpath=Path("data/analysis/market")/f"{d}.json"
        market={}
        if mpath.exists():
            try: market=json.loads(mpath.read_text(encoding="utf-8"))
            except: pass
        records.append({
          "date":d,
          "official_data_date":n.get("official_data_date"),
          "index_close":tw.get("index_close"),
          "index_change":tw.get("index_change"),
          "trade_value_twd":tw.get("trade_value_twd"),
          "verdict":market.get("verdict"),
          "market_status":market.get("status"),
          "score":market.get("score"),
          "freshness":n.get("freshness")
        })
    payload={"status":"ok" if records else "pending","generated_at":datetime.now(TZ).isoformat(),
             "count":len(records),"records":records[-120:]}
    p=OUT/"history";p.mkdir(exist_ok=True)
    (p/"latest.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

def main():
    build_breadth(); build_history()
if __name__=="__main__": main()
