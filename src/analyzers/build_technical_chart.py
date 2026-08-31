from __future__ import annotations
import json, math, statistics
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
HIST=ROOT/'data/history/prices'
DECISION=ROOT/'data/analysis/decision/latest.json'
OUT=ROOT/'public/data/technical_charts'
TZ=ZoneInfo('Asia/Taipei')

def load(p):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except:return {}

def sma(rows,n,field='close'):
    out=[]
    for i,_ in enumerate(rows):
        vals=[x.get(field) for x in rows[max(0,i-n+1):i+1] if isinstance(x.get(field),(int,float))]
        out.append(round(sum(vals)/n,2) if len(vals)==n else None)
    return out

def pivots(rows, field, mode, wing=2):
    pts=[]
    for i in range(wing,len(rows)-wing):
        v=rows[i].get(field)
        if not isinstance(v,(int,float)): continue
        near=[rows[j].get(field) for j in range(i-wing,i+wing+1)]
        if not all(isinstance(x,(int,float)) for x in near): continue
        if (mode=='low' and v==min(near)) or (mode=='high' and v==max(near)):
            pts.append({'index':i,'date':rows[i]['date'],'price':v})
    return pts

def gaps(rows):
    ans=[]
    for i in range(1,len(rows)):
        a,b=rows[i-1],rows[i]
        ah,al,bh,bl=a.get('high'),a.get('low'),b.get('high'),b.get('low')
        if None in (ah,al,bh,bl):continue
        typ=lo=hi=None
        if bl>ah: typ,lo,hi='up',ah,bl
        elif bh<al: typ,lo,hi='down',bh,al
        if not typ: continue
        later=rows[i+1:]; filled=False; partial=False
        if typ=='up':
            filled=any(x.get('low') is not None and x['low']<=lo for x in later)
            partial=(not filled and any(x.get('low') is not None and x['low']<hi for x in later))
        else:
            filled=any(x.get('high') is not None and x['high']>=hi for x in later)
            partial=(not filled and any(x.get('high') is not None and x['high']>lo for x in later))
        ans.append({'date':b.get('date'),'index':i,'type':typ,'low':lo,'high':hi,'status':'filled' if filled else 'partial' if partial else 'unfilled'})
    return ans[-12:]

def make_trendlines(rows):
    lows=pivots(rows,'low','low')[-10:]
    highs=pivots(rows,'high','high')[-10:]
    lines=[]
    def pairs(points, role):
        cand=[]
        for a,b in zip(points[:-1],points[1:]):
            dx=b['index']-a['index']
            if dx<=0: continue
            slope=(b['price']-a['price'])/dx
            direction='ascending' if slope>0 else 'descending' if slope<0 else 'flat'
            cand.append({
                'role':role,'direction':direction,'from':a,'to':b,
                'slope':round(slope,4),'strength':2,'label':f"{'上升' if direction=='ascending' else '下降' if direction=='descending' else '水平'}{'支撐' if role=='support' else '壓力'}"
            })
        return cand[-4:]
    lines += pairs(lows,'support')
    lines += pairs(highs,'resistance')
    return lines[-8:]

def cluster_levels(points, close):
    if not points:return []
    tol=max(close*0.009, 0.01)
    vals=sorted(points,key=lambda x:x['price'])
    groups=[]
    for p in vals:
        if not groups or abs(p['price']-statistics.mean(x['price'] for x in groups[-1]))>tol:
            groups.append([p])
        else: groups[-1].append(p)
    zones=[]
    for g in groups:
        center=statistics.mean(x['price'] for x in g)
        width=max(close*0.0045, (max(x['price'] for x in g)-min(x['price'] for x in g))/2 + close*0.002)
        zones.append({
            'low':round(center-width,2),'high':round(center+width,2),'center':round(center,2),
            'touches':len(g),'last_date':max(x['date'] for x in g),
            'type':'support' if center<=close else 'resistance',
            'source':'pivot_cluster'
        })
    zones.sort(key=lambda z:(-z['touches'],abs(z['center']-close)))
    return zones[:12]

def pct(a,b):
    if a is None or b in (None,0):return None
    return round((a-b)/b*100,2)

def decision_map():
    d=load(DECISION)
    return {str(x.get('code')):x for x in d.get('rankings',[]) if isinstance(x,dict) and x.get('code')}

def zone(center, width_pct, kind, label, source):
    if not isinstance(center,(int,float)) or center<=0:return None
    return {'kind':kind,'label':label,'low':round(center*(1-width_pct),2),'high':round(center*(1+width_pct),2),'center':round(center,2),'source':source}

def decision_zones(dec, rows, ma20, sr_zones):
    if not dec:return []
    t=dec.get('technical') or {}; p=dec.get('trading_plan') or {}
    close=rows[-1]['close']; out=[]
    trigger=p.get('trigger')
    invalid=p.get('invalidation')
    target1=p.get('target1'); target2=p.get('target2')
    supports=[z for z in sr_zones if z['type']=='support']
    resist=[z for z in sr_zones if z['type']=='resistance']
    nearest_sup=max((z for z in supports if z['center']<=close), key=lambda z:z['center'], default=None)
    nearest_res=min((z for z in resist if z['center']>=close), key=lambda z:z['center'], default=None)
    retest_center=trigger or (ma20[-1] if ma20 else None) or (nearest_sup or {}).get('center')
    z=zone(retest_center,0.012,'retest','回測區','decision.trigger/ma20/support')
    if z:out.append(z)
    breakout_center=(nearest_res or {}).get('high') or trigger
    z=zone(breakout_center,0.008,'breakout','突破確認區','nearest_resistance/trigger')
    if z:
        z['low']=round(z['center'],2); z['high']=round(z['center']*1.016,2); out.append(z)
    base=ma20[-1] if ma20 and ma20[-1] else close
    no_chase_low=max(base*1.08, (nearest_res or {}).get('center') or 0)
    if no_chase_low>0:
        out.append({'kind':'no_chase','label':'不追價區','low':round(no_chase_low,2),'high':round(max(no_chase_low*1.06,close*1.04),2),'center':round(no_chase_low,2),'source':'ma20_extension/resistance'})
    if isinstance(invalid,(int,float)) and invalid>0:
        out.append({'kind':'invalidation','label':'失效區','low':round(invalid*0.965,2),'high':round(invalid*1.005,2),'center':round(invalid,2),'source':'decision.invalidation'})
    for val,label in ((target1,'目標一'),(target2,'目標二')):
        if isinstance(val,(int,float)) and val>0:
            out.append({'kind':'target','label':label,'low':val,'high':val,'center':val,'source':'decision.target'})
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    dm=decision_map(); count=0
    for p in HIST.glob('[0-9][0-9][0-9][0-9].json'):
        x=load(p)
        rows=[r for r in x.get('prices',[]) if all(isinstance(r.get(k),(int,float)) for k in ('open','high','low','close'))][-126:]
        if len(rows)<5:continue
        m5,m20,m60,m120=sma(rows,5),sma(rows,20),sma(rows,60),sma(rows,120)
        candles=[]
        for i,r in enumerate(rows):
            candles.append({**{k:r.get(k) for k in ('date','open','high','low','close','volume')},'ma5':m5[i],'ma20':m20[i],'ma60':m60[i],'ma120':m120[i]})
        close=rows[-1]['close']
        gl=gaps(rows)
        tl=make_trendlines(rows)
        pts=pivots(rows,'low','low')[-20:]+pivots(rows,'high','high')[-20:]
        sr=cluster_levels(pts,close)
        # add gap boundaries as structural zones
        for g in gl:
            if g['status']!='filled':
                center=(g['low']+g['high'])/2
                sr.append({'low':g['low'],'high':g['high'],'center':round(center,2),'touches':1,'last_date':g['date'],
                           'type':'support' if center<=close else 'resistance','source':'gap'})
        sr=sorted(sr,key=lambda z:(abs(z['center']-close),-z.get('touches',1)))[:14]
        dec=dm.get(str(x.get('code'))) or {}
        dz=decision_zones(dec,rows,m20,sr)
        payload={
          'schema_version':'5.4.43-chart-decision-overlay',
          'generated_at':datetime.now(TZ).isoformat(),'code':x.get('code'),'name':x.get('name'),'market':x.get('market'),
          'record_count':len(candles),'first_date':candles[0]['date'],'last_date':candles[-1]['date'],
          'candles':candles,'gaps':gl,'trendlines':tl,'support_resistance_zones':sr,'decision_zones':dz,
          'decision_snapshot':{
             'score':dec.get('decision_score'),'grade':dec.get('grade'),'card_label':dec.get('card_label'),
             'action':(dec.get('trading_plan') or {}).get('action'),'trigger':(dec.get('trading_plan') or {}).get('trigger'),
             'invalidation':(dec.get('trading_plan') or {}).get('invalidation'),'target1':(dec.get('trading_plan') or {}).get('target1'),
             'target2':(dec.get('trading_plan') or {}).get('target2'),'risk_pct':(dec.get('trading_plan') or {}).get('risk_pct'),
             'rr1':(dec.get('trading_plan') or {}).get('rr1')
          }
        }
        (OUT/f"{x.get('code')}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');count+=1
    (OUT/'_status.json').write_text(json.dumps({'schema_version':'5.4.43-chart-decision-overlay','generated_at':datetime.now(TZ).isoformat(),'chart_count':count},ensure_ascii=False,indent=2),encoding='utf-8')
    print('technical charts',count)

if __name__=='__main__':main()
