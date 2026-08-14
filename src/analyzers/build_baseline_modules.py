from __future__ import annotations
import json, re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

TZ=ZoneInfo("Asia/Taipei")
OUT=Path("data/analysis/baseline")
OUT.mkdir(parents=True,exist_ok=True)

def latest(folder):
    fs=sorted(Path(folder).glob("20*.json"))
    if not fs: return {}
    return json.loads(fs[-1].read_text(encoding="utf-8"))

def num(v):
    if v is None:return None
    s=str(v).replace(",","").replace("%","").strip()
    if s in ("","--","-"):return None
    try:return float(s)
    except:return None

def first(row,*keys):
    for k in keys:
        if k in row and row[k] not in (None,""): return row[k]
    return None

def dateval(row):
    return first(row,"Date","date","TradeDate","TradingDate","日期")

def latest_rows(rows):
    if not isinstance(rows,list): return []
    ds=[str(dateval(x)) for x in rows if isinstance(x,dict) and dateval(x)]
    if not ds:return rows
    d=max(ds)
    return [x for x in rows if isinstance(x,dict) and str(dateval(x))==d]

def build_margin(twse):
    rows=twse.get("datasets",{}).get("margin_balance",[])
    rows=latest_rows(rows)
    total={}
    # MI_MARGN contains both aggregate and security rows depending on API version.
    for r in rows:
        if not isinstance(r,dict):continue
        label=str(first(r,"股票代號","Code","Item","項目","名稱") or "")
        if label and not re.fullmatch(r"\d{4,6}",label):
            for k,v in r.items():
                if any(t in str(k) for t in ("融資餘額","融券餘額","MarginPurchase","ShortSale")):
                    total[str(k)]=num(v)
    return {"status":"ok" if rows else "pending","data_date":twse.get("official_data_date"),
            "generated_at":datetime.now(TZ).isoformat(),"source":"TWSE MI_MARGN",
            "summary":total,"row_count":len(rows)}

def build_putcall(taifex):
    rows=taifex.get("datasets",{}).get("put_call_ratio",[])
    rows=latest_rows(rows)
    r=rows[0] if rows else {}
    ratio=None
    for k,v in r.items():
        lk=str(k).lower()
        if "ratio" in lk or "比率" in str(k):
            n=num(v)
            if n is not None: ratio=n; break
    return {"status":"ok" if rows else "pending","data_date":str(dateval(r) or "") or None,
            "generated_at":datetime.now(TZ).isoformat(),"source":"TAIFEX PutCallRatio",
            "value":ratio,"latest":r}

def build_lending(twse):
    rows=twse.get("datasets",{}).get("margin_balance",[])
    candidates=[]
    for r in rows if isinstance(rows,list) else []:
        if not isinstance(r,dict):continue
        keys=" ".join(map(str,r.keys()))
        if "借券" in keys or "SBL" in keys.upper():
            candidates.append(r)
    return {"status":"ok" if candidates else "pending","data_date":twse.get("official_data_date"),
            "generated_at":datetime.now(TZ).isoformat(),"source":"TWSE available datasets",
            "items":candidates[:50],
            "note":None if candidates else "目前 TWSE 快照未含可辨識借券欄位；保留待接狀態，不虛構。"}

def classify_securities(twse):
    rows=twse.get("datasets",{}).get("stock_prices",[])
    etf=[]; warrant=[]
    for r in rows if isinstance(rows,list) else []:
        if not isinstance(r,dict):continue
        code=str(first(r,"Code","證券代號","股票代號") or "")
        name=str(first(r,"Name","證券名稱","股票名稱") or "")
        vol=num(first(r,"TradeVolume","成交股數","成交量")) or 0
        chg=num(first(r,"Change","漲跌價差","ChangePercent"))
        item={"code":code,"name":name,"volume":vol,"change":chg}
        if re.match(r"^00\d{3}",code) or "ETF" in name.upper(): etf.append(item)
        if len(code)>=5 and (code[0] in "0" or "購" in name or "售" in name): warrant.append(item)
    etf.sort(key=lambda x:x["volume"],reverse=True); warrant.sort(key=lambda x:x["volume"],reverse=True)
    d=twse.get("official_data_date")
    return ({"status":"ok" if etf else "pending","data_date":d,"generated_at":datetime.now(TZ).isoformat(),
             "source":"TWSE STOCK_DAY_ALL","items":etf[:30]},
            {"status":"ok" if warrant else "pending","data_date":d,"generated_at":datetime.now(TZ).isoformat(),
             "source":"TWSE STOCK_DAY_ALL","items":warrant[:30]})

def build_vix():
    try:
        u="https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?range=5d&interval=1d"
        j=requests.get(u,headers={"User-Agent":"Mozilla/5.0"},timeout=20).json()
        r=j["chart"]["result"][0]; ts=r["timestamp"]; q=r["indicators"]["quote"][0]["close"]
        pairs=[(t,v) for t,v in zip(ts,q) if v is not None]
        t,v=pairs[-1]
        d=datetime.fromtimestamp(t,TZ).date().isoformat()
        return {"status":"ok","data_date":d,"generated_at":datetime.now(TZ).isoformat(),
                "source":"CBOE VIX via public market quote","value":round(float(v),2)}
    except Exception as e:
        return {"status":"pending","data_date":None,"generated_at":datetime.now(TZ).isoformat(),
                "source":"VIX quote","error":str(e),"note":"VIX 取得失敗時保留 pending，不阻擋台股盤後發布。"}

def save(name,p):
    (OUT/f"{name}.json").write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding="utf-8")

def main():
    twse=latest("data/raw/twse"); taifex=latest("data/raw/taifex")
    save("margin",build_margin(twse))
    save("securities_lending",build_lending(twse))
    save("putcall",build_putcall(taifex))
    save("vix",build_vix())
    etf,warrant=classify_securities(twse); save("etf",etf); save("warrant",warrant)
    return 0
if __name__=="__main__": raise SystemExit(main())
