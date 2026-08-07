from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TAIPEI=ZoneInfo('Asia/Taipei')
OUT=Path('public/data')
SOURCES={
 'market':Path('data/analysis/market/latest.json'),
 'institutional':Path('data/analysis/institutional/latest.json'),
 'sectors':Path('data/analysis/sectors/latest.json'),
 'capital_flow':Path('data/analysis/capital_flow/latest.json'),
 'research':Path('data/analysis/research/latest.json'),
}
def read(path):
    try:
        x=json.loads(path.read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {'status':'pending'}
    except Exception as e:
        return {'status':'pending','error':str(e),'source':str(path)}
def data_date(name,p):
    return p.get('data_date') or p.get('official_data_date') or p.get('run_date')
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    payloads={k:read(v) for k,v in SOURCES.items()}
    dates={}
    for k,p in payloads.items():
        dates[k]=data_date(k,p)
        (OUT/f'{k}.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
    valid=sorted({d for d in dates.values() if isinstance(d,str)})
    meta={
      'schema_version':'4.2',
      'generated_at':datetime.now(TAIPEI).isoformat(),
      'latest_available_data_date':max(valid) if valid else None,
      'latest_common_data_date':min(valid) if valid else None,
      'module_dates':dates,
      'date_consistency':'ok' if len(valid)<=1 else 'mixed',
      'modules':{k:p.get('status','pending') for k,p in payloads.items()},
      'warning':None if len(valid)<=1 else '各模組資料日期不一致，請依各模組日期判讀。'
    }
    (OUT/'meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
