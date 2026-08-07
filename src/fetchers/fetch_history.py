from __future__ import annotations
import json, logging, re, sys, time
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import requests

TAIPEI=ZoneInfo("Asia/Taipei")
SECTOR_CONFIG_PATH=Path("config/sectors.json")
HOT_CONFIG_PATH=Path("config/hot_stocks.json")
OUTPUT_ROOT=Path("data/history/prices")
LOG=logging.getLogger("fetch_history")
TWSE_URL="https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
TPEX_URL="https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php"

def setup_logging():
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s - %(message)s")

def load_json(path): return json.loads(path.read_text(encoding="utf-8"))

def request_json(url,*,params,attempts=3,timeout=45):
    headers={"User-Agent":"daily-focus-brief/5.1.1","Accept":"application/json,text/plain,*/*","Referer":"https://www.twse.com.tw/"}
    last=None
    for attempt in range(1,attempts+1):
        try:
            r=requests.get(url,params=params,headers=headers,timeout=timeout);r.raise_for_status();return r.json()
        except (requests.RequestException,ValueError) as exc:
            last=exc;LOG.warning("Request failed %s/%s: %s",attempt,attempts,exc)
            if attempt<attempts: time.sleep(2**(attempt-1))
    raise RuntimeError(str(last))

def month_starts(month_count=6):
    today=datetime.now(TAIPEI).date();year,month=today.year,today.month;out=[]
    for _ in range(month_count):
        out.append(date(year,month,1));month-=1
        if month==0: year-=1;month=12
    return sorted(out)

def number(v):
    t=str(v or "").replace(",","").replace("+","").strip()
    if t in {"","--","---","除權","除息","除權息"}: return None
    try:return float(t)
    except ValueError:return None

def roc_date_to_iso(v):
    p=re.findall(r"\d+",str(v or ""))
    if len(p)<3:return None
    try:return date(int(p[0])+1911,int(p[1]),int(p[2])).isoformat()
    except ValueError:return None

def parse_twse(payload):
    if not isinstance(payload,dict) or payload.get("stat")!="OK": return []
    out=[]
    for row in payload.get("data",[]):
        if not isinstance(row,list) or len(row)<9: continue
        d,c=roc_date_to_iso(row[0]),number(row[6])
        if not d or c is None: continue
        out.append({"date":d,"volume":number(row[1]),"trade_value":number(row[2]),"open":number(row[3]),"high":number(row[4]),"low":number(row[5]),"close":c,"change":number(row[7]),"transactions":number(row[8])})
    return out

def parse_tpex(payload):
    if not isinstance(payload,dict): return []
    rows=payload.get("aaData") or payload.get("data") or payload.get("tables") or []
    if isinstance(rows,dict): rows=rows.get("data",[])
    out=[]
    for row in rows:
        if isinstance(row,dict):
            d=roc_date_to_iso(row.get("Date") or row.get("日期") or row.get("TradeDate"));c=number(row.get("Close") or row.get("收盤價") or row.get("ClosingPrice"))
            if d and c is not None:
                out.append({"date":d,"volume":number(row.get("Volume") or row.get("成交股數")),"trade_value":number(row.get("Amount") or row.get("成交金額")),"open":number(row.get("Open") or row.get("開盤價")),"high":number(row.get("High") or row.get("最高價")),"low":number(row.get("Low") or row.get("最低價")),"close":c,"change":number(row.get("Change") or row.get("漲跌")),"transactions":number(row.get("Transactions") or row.get("成交筆數"))})
            continue
        if not isinstance(row,list) or len(row)<7: continue
        d,c=roc_date_to_iso(row[0]),number(row[6])
        if d and c is not None:
            out.append({"date":d,"volume":number(row[1]),"trade_value":number(row[2]),"open":number(row[3]),"high":number(row[4]),"low":number(row[5]),"close":c,"change":number(row[7] if len(row)>7 else None),"transactions":number(row[8] if len(row)>8 else None)})
    return out

def fetch_twse(code,months):
    rows=[]
    for m in months:
        rows.extend(parse_twse(request_json(TWSE_URL,params={"response":"json","date":m.strftime("%Y%m%d"),"stockNo":code})));time.sleep(.28)
    return rows

def fetch_tpex(code,months):
    rows=[]
    for m in months:
        rows.extend(parse_tpex(request_json(TPEX_URL,params={"l":"zh-tw","d":f"{m.year-1911}/{m.month:02d}","stkno":code})));time.sleep(.28)
    return rows

def codes_from_config(path,key):
    if not path.exists(): return set()
    cfg=load_json(path)
    return {str(c) for g in cfg.get(key,[]) for c in g.get("members",[]) if str(c).isdigit()}

def unique_codes():
    return sorted(codes_from_config(SECTOR_CONFIG_PATH,"sectors")|codes_from_config(HOT_CONFIG_PATH,"groups"))

def merge_rows(existing,new):
    merged={str(r.get("date")):r for r in existing+new if r.get("date") and r.get("close") is not None}
    return [merged[k] for k in sorted(merged)]

def load_existing(code):
    p=OUTPUT_ROOT/f"{code}.json"
    if not p.exists():return []
    try:
        rows=load_json(p).get("prices",[]);return rows if isinstance(rows,list) else []
    except Exception:return []

def save(code,market,rows):
    OUTPUT_ROOT.mkdir(parents=True,exist_ok=True)
    payload={"schema_version":"5.1.1","code":code,"market":market,"updated_at":datetime.now(TAIPEI).isoformat(),"record_count":len(rows),"first_date":rows[0]["date"] if rows else None,"last_date":rows[-1]["date"] if rows else None,"prices":rows}
    (OUTPUT_ROOT/f"{code}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

def main():
    setup_logging();months=month_starts(6);codes=unique_codes();failures=[];successes=[]
    for i,code in enumerate(codes,1):
        LOG.info("Fetching %s (%s/%s)",code,i,len(codes))
        try:
            rows=fetch_twse(code,months);market="TWSE" if rows else "unknown"
            if not rows:
                rows=fetch_tpex(code,months);market="TPEx" if rows else "unknown"
            if not rows:
                failures.append({"code":code,"error":"No official historical rows returned"});continue
            merged=merge_rows(load_existing(code),rows);save(code,market,merged);successes.append({"code":code,"market":market,"record_count":len(merged)})
        except Exception as exc:
            LOG.exception("Failed %s",code);failures.append({"code":code,"error":str(exc)})
    summary={"generated_at":datetime.now(TAIPEI).isoformat(),"requested_codes":len(codes),"success_count":len(successes),"failed_count":len(failures),"successful_codes":successes,"failed_codes":failures}
    OUTPUT_ROOT.mkdir(parents=True,exist_ok=True);(OUTPUT_ROOT/"_status.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False));return 0

if __name__=="__main__":sys.exit(main())
