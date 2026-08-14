from __future__ import annotations
import json, re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

TZ=ZoneInfo("Asia/Taipei")
OUT=Path("data/analysis/baseline"); OUT.mkdir(parents=True,exist_ok=True)

def latest(folder):
    fs=sorted(Path(folder).glob("20*.json"))
    return json.loads(fs[-1].read_text(encoding="utf-8")) if fs else {}

def num(v):
    if v is None:return None
    s=str(v).replace(",","").replace("%","").strip()
    try:return float(s) if s not in ("","--","-") else None
    except:return None

def first(r,*ks):
    for k in ks:
        if k in r and r[k] not in (None,""):return r[k]
    return None

def save(n,p):(OUT/f"{n}.json").write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding="utf-8")

def build_margin(twse):
    rows=twse.get("datasets",{}).get("margin_balance",[])
    # Aggregate from security rows. TWSE MI_MARGN column names vary by snapshot.
    m_bal=s_bal=m_buy=m_sell=s_sell=s_buy=0.0; usable=0
    items=[]
    for r in rows if isinstance(rows,list) else []:
        if not isinstance(r,dict):continue
        code=str(first(r,"Code","股票代號","證券代號","股票代碼") or "")
        if not re.fullmatch(r"\d{4,6}",code):continue
        mb=num(first(r,"MarginPurchaseTodayBalance","融資今日餘額","融資餘額","融資今日餘額(張)"))
        sb=num(first(r,"ShortSaleTodayBalance","融券今日餘額","融券餘額","融券今日餘額(張)"))
        mbuy=num(first(r,"MarginPurchase","融資買進")) or 0
        msell=num(first(r,"MarginPurchaseCashRepayment","融資賣出","融資現金償還")) or 0
        ssell=num(first(r,"ShortSale","融券賣出")) or 0
        sbuy=num(first(r,"ShortSaleCashRepayment","融券買進","融券現券償還")) or 0
        if mb is not None or sb is not None:
            usable+=1; m_bal+=mb or 0; s_bal+=sb or 0; m_buy+=mbuy; m_sell+=msell; s_sell+=ssell; s_buy+=sbuy
            items.append({"code":code,"name":first(r,"Name","股票名稱","證券名稱"),"margin_balance":mb,"short_balance":sb})
    summary={"margin_balance":m_bal,"short_balance":s_bal,"margin_buy":m_buy,"margin_repayment_or_sell":m_sell,
             "short_sell":s_sell,"short_repayment_or_buy":s_buy} if usable else {}
    return {"status":"ok" if usable else "pending","data_date":twse.get("official_data_date"),
            "generated_at":datetime.now(TZ).isoformat(),"source":"TWSE MI_MARGN","summary":summary,
            "row_count":len(rows),"usable_rows":usable,"items":items[:50],
            "note":None if usable else "MI_MARGN 已取得，但欄位名稱與解析規則仍未匹配；不顯示空 summary 為有效資料。"}

def build_putcall(taifex):
    rows=taifex.get("datasets",{}).get("put_call_ratio",[])
    r=rows[-1] if rows else {}
    return {"status":"ok" if r else "pending","data_date":first(r,"Date","date"),
            "generated_at":datetime.now(TZ).isoformat(),"source":"TAIFEX PutCallRatio",
            "value":num(first(r,"PutCallVolumeRatio%","PutCallRatio","買賣權成交量比率")),
            "oi_ratio":num(first(r,"PutCallOIRatio%","買賣權未平倉量比率")),"latest":r}

def build_lending(twse):
    d=str(twse.get("official_data_date") or "").replace("-","")
    try:
        u=f"https://www.twse.com.tw/exchangeReport/TWT93U?response=json&date={d}"
        j=requests.get(u,headers={"User-Agent":"Mozilla/5.0"},timeout=25).json()
        fields=j.get("fields") or []; data=j.get("data") or []
        items=[]; total=0
        for row in data:
            rec=dict(zip(fields,row))
            code=str(row[0]).strip() if row else ""
            name=str(row[1]).strip() if len(row)>1 else ""
            # TWT93U layout: code,name, 6 short-sale cols, then lending previous/sell/return/adjust/balance/limit
            bal=num(row[12]) if len(row)>12 else None
            sold=num(row[9]) if len(row)>9 else None
            returned=num(row[10]) if len(row)>10 else None
            if bal is not None:
                total+=bal
                items.append({"code":code,"name":name,"lending_sell":sold,"returned":returned,"balance":bal})
        items.sort(key=lambda x:x["balance"] or 0,reverse=True)
        return {"status":"ok" if items else "pending","data_date":twse.get("official_data_date"),
                "generated_at":datetime.now(TZ).isoformat(),"source":"TWSE TWT93U",
                "summary":{"lending_sell_balance":total} if items else {},"items":items[:50]}
    except Exception as e:
        return {"status":"pending","data_date":twse.get("official_data_date"),"generated_at":datetime.now(TZ).isoformat(),
                "source":"TWSE TWT93U","error":str(e)}

def classify(twse):
    rows=twse.get("datasets",{}).get("stock_prices",[]); etf=[]; warrant=[]
    for r in rows if isinstance(rows,list) else []:
        code=str(first(r,"Code","證券代號","股票代號") or ""); name=str(first(r,"Name","證券名稱","股票名稱") or "")
        item={"code":code,"name":name,"volume":num(first(r,"TradeVolume","成交股數","成交量")) or 0,
              "change":num(first(r,"Change","漲跌價差","ChangePercent"))}
        # ETFs/funds: common 00xxxx codes, including active A/B/D suffix products.
        is_etf=bool(re.fullmatch(r"00\d{3}[A-Z]?",code)) or "ETF" in name.upper()
        # TWSE warrants are normally 6 chars and names explicitly contain 購/售.
        is_warrant=bool(re.fullmatch(r"\d{5,6}[A-Z]?",code)) and ("購" in name or "售" in name) and not is_etf
        if is_etf:etf.append(item)
        if is_warrant:warrant.append(item)
    etf.sort(key=lambda x:x["volume"],reverse=True); warrant.sort(key=lambda x:x["volume"],reverse=True)
    d=twse.get("official_data_date"); now=datetime.now(TZ).isoformat()
    return ({"status":"ok" if etf else "pending","data_date":d,"generated_at":now,"source":"TWSE STOCK_DAY_ALL","items":etf[:30]},
            {"status":"ok" if warrant else "pending","data_date":d,"generated_at":now,"source":"TWSE STOCK_DAY_ALL",
             "items":warrant[:30],"note":None if warrant else "STOCK_DAY_ALL 未提供可辨識權證時維持 pending，不以 ETF 代替。"})

def build_vix():
    try:
        j=requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?range=5d&interval=1d",
                       headers={"User-Agent":"Mozilla/5.0"},timeout=20).json()["chart"]["result"][0]
        pairs=[(t,v) for t,v in zip(j["timestamp"],j["indicators"]["quote"][0]["close"]) if v is not None]
        t,v=pairs[-1]
        return {"status":"ok","data_date":datetime.fromtimestamp(t,TZ).date().isoformat(),
                "generated_at":datetime.now(TZ).isoformat(),"source":"CBOE VIX via public market quote","value":round(float(v),2)}
    except Exception as e:return {"status":"pending","generated_at":datetime.now(TZ).isoformat(),"source":"VIX quote","error":str(e)}

def main():
    twse=latest("data/raw/twse"); taifex=latest("data/raw/taifex")
    save("margin",build_margin(twse)); save("securities_lending",build_lending(twse))
    save("putcall",build_putcall(taifex)); save("vix",build_vix())
    e,w=classify(twse);save("etf",e);save("warrant",w)
if __name__=="__main__":main()
