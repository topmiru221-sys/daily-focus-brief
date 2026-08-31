from __future__ import annotations
import json, math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]; HIST=ROOT/'data/history/prices'; OUT=ROOT/'public/data/technical_charts'; TZ=ZoneInfo('Asia/Taipei')
def load(p):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except:return {}
def sma(rows,n):
 out=[]
 for i,r in enumerate(rows):
  vals=[x.get('close') for x in rows[max(0,i-n+1):i+1] if isinstance(x.get('close'),(int,float))]
  out.append(round(sum(vals)/n,2) if len(vals)==n else None)
 return out
def gaps(rows):
 ans=[]
 for i in range(1,len(rows)):
  a,b=rows[i-1],rows[i]; ah,al=a.get('high'),a.get('low'); bh,bl=b.get('high'),b.get('low')
  if None in (ah,al,bh,bl):continue
  typ=lo=hi=None
  if bl>ah:typ,lo,hi='up',ah,bl
  elif bh<al:typ,lo,hi='down',bh,al
  if not typ:continue
  later=rows[i+1:]; filled=False; partial=False
  if typ=='up':
   filled=any(x.get('low') is not None and x['low']<=lo for x in later); partial=(not filled and any(x.get('low') is not None and x['low']<hi for x in later))
  else:
   filled=any(x.get('high') is not None and x['high']>=hi for x in later); partial=(not filled and any(x.get('high') is not None and x['high']>lo for x in later))
  ans.append({'date':b.get('date'),'type':typ,'low':lo,'high':hi,'status':'filled' if filled else 'partial' if partial else 'unfilled'})
 return ans[-8:]
def pivots(rows,field,mode):
 pts=[]
 for i in range(2,len(rows)-2):
  v=rows[i].get(field)
  if v is None:continue
  near=[rows[j].get(field) for j in range(i-2,i+3) if rows[j].get(field) is not None]
  if len(near)==5 and (v==min(near) if mode=='low' else v==max(near)):pts.append({'index':i,'date':rows[i]['date'],'price':v})
 return pts[-6:]
def trend(rows):
 lows=pivots(rows,'low','low'); highs=pivots(rows,'high','high'); out={}
 if len(lows)>=2:
  a,b=lows[-2:]; out['support']={'from':a,'to':b,'slope':round((b['price']-a['price'])/(b['index']-a['index']),4)}
 if len(highs)>=2:
  a,b=highs[-2:]; out['resistance']={'from':a,'to':b,'slope':round((b['price']-a['price'])/(b['index']-a['index']),4)}
 return out
def main():
 OUT.mkdir(parents=True,exist_ok=True); count=0
 for p in HIST.glob('[0-9][0-9][0-9][0-9].json'):
  x=load(p); rows=[r for r in x.get('prices',[]) if all(r.get(k) is not None for k in ('open','high','low','close'))][-126:]
  if len(rows)<5:continue
  m5,m20,m60=sma(rows,5),sma(rows,20),sma(rows,60)
  candles=[]
  for i,r in enumerate(rows):candles.append({**{k:r.get(k) for k in ('date','open','high','low','close','volume')},'ma5':m5[i],'ma20':m20[i],'ma60':m60[i]})
  payload={'schema_version':'5.4.42-technical-chart','generated_at':datetime.now(TZ).isoformat(),'code':x.get('code'),'name':x.get('name'),'market':x.get('market'),'record_count':len(candles),'first_date':candles[0]['date'],'last_date':candles[-1]['date'],'candles':candles,'gaps':gaps(rows),'trendlines':trend(rows)}
  (OUT/f"{x.get('code')}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');count+=1
 (OUT/'_status.json').write_text(json.dumps({'schema_version':'5.4.42-technical-chart','generated_at':datetime.now(TZ).isoformat(),'chart_count':count},ensure_ascii=False,indent=2),encoding='utf-8')
 print('technical charts',count)
if __name__=='__main__':main()
