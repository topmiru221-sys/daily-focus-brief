from __future__ import annotations
import json, sys
from datetime import datetime
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from src.indicators.technical import calculate, num
from src.rules.trading_rules import evaluate

TAIPEI=ZoneInfo("Asia/Taipei")
RESEARCH_PATH=Path("data/analysis/research/latest.json")
SECTOR_PATH=Path("data/analysis/sectors/latest.json")
FLOW_PATH=Path("data/analysis/flow_persistence/latest.json")
HISTORY_ROOT=Path("data/history/prices")
OUTPUT_ROOT=Path("data/analysis/decision")
RAW_ROOT=Path("data/raw")
PRIORITY_PATH=Path("data/analysis/priority_history_universe.json")

def load_json(path):
    try:
        v=json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v,dict) else {}
    except Exception:return {}

def avg(values):
    values=[v for v in values if v is not None]
    return mean(values) if values else None

def grade(score):
    return "S" if score>=90 else "A" if score>=80 else "B" if score>=70 else "C" if score>=60 else "D"

def latest_universe():
    out={}
    specs=(("twse","stock_prices","Code","Name","ClosingPrice","TradeVolume","TWSE"),("tpex","daily_close_quotes","SecuritiesCompanyCode","CompanyName","Close","TradingShares","TPEx"))
    for folder,key,ck,nk,pk,vk,market in specs:
        files=sorted((RAW_ROOT/folder).glob("*.json"))
        if not files: continue
        payload=load_json(files[-1]); day=payload.get("data_date") or files[-1].stem
        for row in payload.get("datasets",{}).get(key,[]):
            code=str(row.get(ck) or "").strip(); price=num(row.get(pk))
            if len(code)==4 and code.isdigit() and price is not None and price>0: out[code]={"name":row.get(nk) or code,"market":market,"date":day,"close":price,"volume":num(row.get(vk))}
    return out

def metrics(code,quote=None):
    payload=load_json(HISTORY_ROOT/f"{code}.json")
    rows=[r for r in payload.get("prices",[]) if isinstance(r,dict) and (num(r.get("close")) or 0)>0] if isinstance(payload.get("prices"),list) else []
    if quote and not any(r.get("date")==quote["date"] for r in rows): rows=rows+[{"date":quote["date"],"close":quote["close"],"open":quote["close"],"high":quote["close"],"low":quote["close"],"volume":quote.get("volume")}]
    return calculate(rows)

def main():
    now=datetime.now(TAIPEI)
    research,sectors,flow=[load_json(p) for p in (RESEARCH_PATH,SECTOR_PATH,FLOW_PATH)]
    sector_by_name={str(r.get("name")):r for r in sectors.get("rankings",[]) if isinstance(r,dict)}
    flow_by_name={str(r.get("sector_name")):r for r in flow.get("rankings",[]) if isinstance(r,dict)}

    stock_meta={}
    for sector in sectors.get("rankings",[]):
        if not isinstance(sector,dict):continue
        sname=str(sector.get("name") or "")
        reps={str(r.get("code")):r for r in sector.get("representatives",[]) if isinstance(r,dict) and r.get("code")}
        for code in sector.get("members",[]):
            code=str(code)
            m=stock_meta.setdefault(code,{"code":code,"name":code,"market":None,"sectors":[]})
            if sname and sname not in m["sectors"]:m["sectors"].append(sname)
            if code in reps:
                m["name"]=reps[code].get("name") or m["name"];m["market"]=reps[code].get("market") or m["market"]

    pool_map={}
    for pool_name,key in [("research","research_pool"),("watch","watch_pool"),("avoid","avoid_pool")]:
        for item in research.get(key,[]):
            if not isinstance(item,dict) or not item.get("code"):continue
            code=str(item["code"]);x=dict(item);x["source_pool"]=pool_name;pool_map[code]=x
            m=stock_meta.setdefault(code,{"code":code,"name":code,"market":None,"sectors":[]})
            m["name"]=item.get("name") or m["name"];m["market"]=item.get("market") or m["market"]
            for s in item.get("sectors",[]):
                if s not in m["sectors"]:m["sectors"].append(s)

    universe=latest_universe(); history_codes=sorted(p.stem for p in HISTORY_ROOT.glob("*.json") if not p.name.startswith("_"))
    all_codes=sorted(universe)
    decisions=[]

    for code in all_codes:
        pool=pool_map.get(code,{})
        meta=stock_meta.get(code,{"name":code,"market":None,"sectors":[]})
        quote=universe.get(code); technical=metrics(code,quote)
        records=technical.get("record_count",0); current=bool(quote and technical.get("price_date")==quote.get("date"))
        card_level="complete" if current and records>=60 else "watch" if current and records>=20 else "basic"
        card_label={"complete":"完整 Decision Card","watch":"技術觀察卡","basic":"即時基礎卡"}[card_level]
        rule=evaluate(technical if card_level!="basic" else {"status":"missing"})
        if card_level!="complete": rule["trading_plan"]={"action":"歷史資料累積中，暫不建立交易計畫","trigger":None,"invalidation":None,"target1":None,"target2":None,"risk_pct":None,"rr1":None}
        sector_names=list(dict.fromkeys(list(pool.get("sectors",[]))+list(meta.get("sectors",[]))))
        sector_rows=[sector_by_name[s] for s in sector_names if s in sector_by_name]
        flow_rows=[flow_by_name[s] for s in sector_names if s in flow_by_name]

        sector_score=avg([num(r.get("average_change_pct"))*8+50 for r in sector_rows if num(r.get("average_change_pct")) is not None])
        sector_score=max(0,min(100,sector_score)) if sector_score is not None else 50
        flow_score=avg([num(r.get("average_score")) or num(r.get("latest_score")) for r in flow_rows]) or 50
        institution_score=50
        if sector_rows:
            inst=sum(num(r.get("institutional_net_shares_top50_scope")) or 0 for r in sector_rows)
            institution_score=max(0,min(100,50+inst/2_000_000*5))

        research_score=num(pool.get("score")) if pool else 50
        technical_score=rule["technical_score"]
        risk_score=rule["risk_quality_score"]
        decision=research_score*.22+sector_score*.20+flow_score*.18+institution_score*.15+technical_score*.15+risk_score*.10
        if pool.get("source_pool")=="avoid":decision=min(decision,59)
        decision=round(max(0,min(100,decision)),1)

        confidence_parts=[
            technical.get("record_count",0)>=20,
            technical.get("record_count",0)>=60,
            bool(sector_rows),bool(flow_rows),bool(pool)
        ]
        confidence=round(sum(confidence_parts)/len(confidence_parts)*100,1)
        if card_level=="basic": confidence=min(confidence,20.0)
        elif card_level=="watch": confidence=min(confidence,60.0)

        reasons=list(dict.fromkeys(list(pool.get("reasons") or [])+rule["reasons"]))[:12]
        flags=list(dict.fromkeys(list(pool.get("risk_flags") or [])+rule["risk_flags"]))[:12]

        decisions.append({
            "code":code,"name":pool.get("name") or (quote or {}).get("name") or meta.get("name") or code,
            "market":pool.get("market") or (quote or {}).get("market") or meta.get("market"),"source_pool":pool.get("source_pool") or "general",
            "sectors":sector_names,"decision_score":decision,"grade":grade(decision),"confidence_pct":confidence,
            "card_level":card_level,"card_label":card_label,"history_record_count":records,"latest_price_current":current,
            "components":{"research":round(research_score,1),"sector":round(sector_score,1),"flow":round(flow_score,1),
                          "institution":round(institution_score,1),"technical":round(technical_score,1),"risk_quality":round(risk_score,1)},
            "technical":technical,"trading_plan":rule["trading_plan"],"reasons":reasons,"risk_flags":flags,
            "conclusion":rule["trading_plan"]["action"]
        })

    decisions.sort(key=lambda r:(r["decision_score"],r["confidence_pct"]),reverse=True)
    priority_payload=load_json(PRIORITY_PATH); priority_codes={str(r.get("code")) for r in priority_payload.get("stocks",[])}
    priority_complete=sum(r.get("code") in priority_codes and r.get("history_record_count",0)>=120 for r in decisions)
    payload={
        "schema_version":"5.4.40-priority-120d","generated_at":now.isoformat(),"data_date":research.get("data_date"),
        "status":"ok" if decisions else "pending","decision_count":len(decisions),
        "history_coverage_count":sum(r.get("card_level")=="complete" for r in decisions),"daily_history_count":len(history_codes),
        "universe_count":len(universe),"universe_source":"daily official TWSE + TPEx 4-digit equity candidates",
        "priority_120d":{"target_count":len(priority_codes),"complete_count":priority_complete,"pending_count":max(0,len(priority_codes)-priority_complete),"target_records":120},
        "rankings":decisions,
        "research_pool":[r for r in decisions if r["source_pool"]=="research"][:10],
        "watch_pool":[r for r in decisions if r["source_pool"]=="watch"][:10],
        "avoid_pool":[r for r in decisions if r["source_pool"]=="avoid"][:10],
        "methodology":{
            "pipeline":"history → indicators → rules → scores → decision → trading plan",
            "indicators":["MA5","MA10","MA20","MA60","MA120","MA240","RSI14","ATR14","MACD","KD","Bollinger","Volume20","Volume60"],
            "risk_first":"失效條件與回檔風險優先於目標報酬；目標僅作風險報酬比較。",
        },
        "disclaimer":"分析與交易計畫為研究框架，不構成買賣建議。"
    }
    OUTPUT_ROOT.mkdir(parents=True,exist_ok=True)
    text=json.dumps(payload,ensure_ascii=False,indent=2)
    (OUTPUT_ROOT/f"{now.date().isoformat()}.json").write_text(text,encoding="utf-8")
    (OUTPUT_ROOT/"latest.json").write_text(text,encoding="utf-8")
    return 0

if __name__=="__main__":raise SystemExit(main())
