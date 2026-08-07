from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TAIPEI=ZoneInfo('Asia/Taipei')
CONFIG=Path('config/sectors.json')
SECTORS=Path('data/analysis/sectors/latest.json')
FLOW=Path('data/analysis/flow_persistence/latest.json')
CAPITAL=Path('data/analysis/capital_flow/latest.json')
DECISION=Path('data/analysis/decision/latest.json')
OUT=Path('data/analysis/sector_center')

def load(path):
    try:
        v=json.loads(path.read_text(encoding='utf-8'))
        return v if isinstance(v,dict) else {}
    except Exception:
        return {}

def main():
    now=datetime.now(TAIPEI)
    cfg,sectors,flow,capital,decision=[load(p) for p in (CONFIG,SECTORS,FLOW,CAPITAL,DECISION)]
    live_by_id={str(x.get('id')):x for x in sectors.get('rankings',[]) if isinstance(x,dict)}
    flow_by_id={str(x.get('sector_id')):x for x in flow.get('rankings',[]) if isinstance(x,dict)}
    capital_by_id={str(x.get('sector_id')):x for x in capital.get('rankings',[]) if isinstance(x,dict)}
    decision_by_code={str(x.get('code')):x for x in decision.get('rankings',[]) if isinstance(x,dict)}
    output=[]
    for definition in cfg.get('sectors',[]):
        sid=str(definition.get('id') or '')
        if not sid: continue
        live,fp,cap=live_by_id.get(sid,{}),flow_by_id.get(sid,{}),capital_by_id.get(sid,{})
        stocks=[]
        for code in definition.get('members',[]):
            code=str(code); d=decision_by_code.get(code)
            if d:
                t=d.get('technical') or {}
                stocks.append({'code':code,'name':d.get('name') or code,'market':d.get('market'),'decision_score':d.get('decision_score'),'grade':d.get('grade'),'confidence_pct':d.get('confidence_pct'),'source_pool':d.get('source_pool'),'close':t.get('close'),'price_date':t.get('price_date'),'ma20':t.get('ma20'),'ma60':t.get('ma60'),'distance_ma20_pct':t.get('distance_ma20_pct'),'distance_ma60_pct':t.get('distance_ma60_pct'),'risk_pct':t.get('risk_pct'),'rr1':t.get('rr1'),'volume_ratio20':t.get('volume_ratio20'),'risk_flags':d.get('risk_flags') or [],'conclusion':d.get('conclusion')})
            else:
                stocks.append({'code':code,'name':code,'market':None,'decision_score':None,'grade':None,'confidence_pct':0,'source_pool':'missing','risk_flags':['尚未完成Decision Card']})
        stocks.sort(key=lambda x:(x.get('decision_score') is not None,x.get('decision_score') or -1,x.get('confidence_pct') or 0),reverse=True)
        leader=stocks[0] if stocks and stocks[0].get('decision_score') is not None else None
        ds=[x['decision_score'] for x in stocks if x.get('decision_score') is not None]
        output.append({'id':sid,'name':definition.get('name'),'member_count':len(definition.get('members',[])),'decision_coverage_count':sum(1 for x in stocks if x.get('decision_score') is not None),'average_decision_score':round(sum(ds)/len(ds),1) if ds else None,'today_rank':live.get('rank'),'average_change_pct':live.get('average_change_pct'),'advance_ratio_pct':live.get('advance_ratio_pct'),'above_20ma_ratio_pct':live.get('above_20ma_ratio_pct'),'above_60ma_ratio_pct':live.get('above_60ma_ratio_pct'),'strong_stock_count':live.get('strong_stock_count'),'classification':live.get('classification'),'flow_score':cap.get('flow_score'),'flow_state':cap.get('flow_state'),'persistence_score':fp.get('average_score'),'persistence_ratio_pct':fp.get('persistence_ratio_pct'),'persistence_state':fp.get('state'),'score_change':fp.get('score_change'),'effective_days':fp.get('effective_days'),'leader':leader,'stocks':stocks})
    output.sort(key=lambda x:(x.get('today_rank') is not None,-(x.get('today_rank') or 999),x.get('flow_score') or 0),reverse=True)
    payload={'schema_version':'5.2-alpha','generated_at':now.isoformat(),'data_date':decision.get('data_date') or sectors.get('run_date'),'status':'ok' if output else 'pending','sector_count':len(output),'sectors':output,'methodology':{'note':'族群成分固定讀取 config/sectors.json；個股決策資料來自 Decision Engine。','leader':'Alpha版先以Decision Score最高且資料可用者作為研究領先股，不等同市場實際主力認定。'}}
    OUT.mkdir(parents=True,exist_ok=True)
    text=json.dumps(payload,ensure_ascii=False,indent=2)
    (OUT/f'{now.date().isoformat()}.json').write_text(text,encoding='utf-8')
    (OUT/'latest.json').write_text(text,encoding='utf-8')
    return 0

if __name__=='__main__': raise SystemExit(main())
