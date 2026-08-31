from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
HIST=ROOT/'data/history/prices'
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

def gaps(rows):
    ans=[]
    for i in range(1,len(rows)):
        a,b=rows[i-1],rows[i]
        ah,al=a.get('high'),a.get('low'); bh,bl=b.get('high'),b.get('low')
        if None in (ah,al,bh,bl):continue
        typ=lo=hi=None
        if bl>ah: typ,lo,hi='up',ah,bl
        elif bh<al: typ,lo,hi='down',bh,al
        if not typ:continue
        later=rows[i+1:]; filled=False; partial=False
        if typ=='up':
            filled=any(x.get('low') is not None and x['low']<=lo for x in later)
            partial=(not filled and any(x.get('low') is not None and x['low']<hi for x in later))
        else:
            filled=any(x.get('high') is not None and x['high']>=hi for x in later)
            partial=(not filled and any(x.get('high') is not None and x['high']>lo for x in later))
        ans.append({'date':b.get('date'),'type':typ,'low':lo,'high':hi,'status':'filled' if filled else 'partial' if partial else 'unfilled'})
    return ans[-8:]

def pivots(rows,field,mode):
    pts=[]
    for i in range(2,len(rows)-2):
        v=rows[i].get(field)
        if v is None:continue
        near=[rows[j].get(field) for j in range(i-2,i+3) if rows[j].get(field) is not None]
        if len(near)==5 and (v==min(near) if mode=='low' else v==max(near)):
            pts.append({'index':i,'date':rows[i]['date'],'price':v})
    return pts[-6:]

def trend(rows):
    lows=pivots(rows,'low','low'); highs=pivots(rows,'high','high'); out={}
    if len(lows)>=2:
        a,b=lows[-2:]
        slope=(b['price']-a['price'])/(b['index']-a['index'])
        if slope>=0:
            out['support']={'from':a,'to':b,'slope':round(slope,4),'structure':'ascending'}
    if len(highs)>=2:
        a,b=highs[-2:]
        slope=(b['price']-a['price'])/(b['index']-a['index'])
        if slope<=0:
            out['resistance']={'from':a,'to':b,'slope':round(slope,4),'structure':'descending'}
    return out

def pct(a,b):
    if a is None or b in (None,0):return None
    return round((a-b)/b*100,2)

def technical_summary(rows,ma20,gaps_list,trendlines):
    close=rows[-1].get('close')
    m20=ma20[-1] if ma20 else None
    v20=sma(rows,20,'volume')[-1] if len(rows)>=20 else None
    vr=round(rows[-1].get('volume')/v20,2) if v20 and rows[-1].get('volume') is not None else None
    current=len(rows)-1
    support=None; resistance=None
    if trendlines.get('support'):
        t=trendlines['support']; support=round(t['from']['price']+t['slope']*(current-t['from']['index']),2)
    if trendlines.get('resistance'):
        t=trendlines['resistance']; resistance=round(t['from']['price']+t['slope']*(current-t['from']['index']),2)
    open_gaps=[g for g in gaps_list if g['status']!='filled']
    nearest=None
    if close is not None and open_gaps:
        def gd(g):
            if g['low']<=close<=g['high']: return 0
            return min(abs(close-g['low']),abs(close-g['high']))
        g=min(open_gaps,key=gd)
        nearest={**g,'distance_pct':round(gd(g)/close*100,2) if close else None}
    ma20_slope=None
    if len(ma20)>=6 and ma20[-1] is not None and ma20[-6] is not None:
        ma20_slope=round(ma20[-1]-ma20[-6],2)
    d20=pct(close,m20)
    supd=pct(close,support) if support else None
    resd=round((resistance-close)/close*100,2) if resistance and close else None
    if support and close<support:
        posture='🔴 技術風險'
    elif d20 is not None and d20>8:
        posture='🟡 不追價'
    elif resd is not None and 0<=resd<=3:
        posture='🟡 不追價'
    elif ma20_slope is not None and ma20_slope>0 and support and close>=support:
        posture='🟢 可等待回測'
    else:
        posture='⚪ 中性觀察'
    return {
        'close':close,'ma20':m20,'distance_to_ma20_pct':d20,'ma20_5d_slope':ma20_slope,
        'volume_ratio20':vr,'nearest_open_gap':nearest,
        'support_trend_price':support,'support_distance_pct':supd,
        'resistance_trend_price':resistance,'resistance_distance_pct':resd,
        'technical_posture':posture
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True); count=0
    for p in HIST.glob('[0-9][0-9][0-9][0-9].json'):
        x=load(p)
        rows=[r for r in x.get('prices',[]) if all(r.get(k) is not None for k in ('open','high','low','close'))][-126:]
        if len(rows)<5:continue
        m5,m20,m60=sma(rows,5),sma(rows,20),sma(rows,60)
        candles=[]
        for i,r in enumerate(rows):
            candles.append({**{k:r.get(k) for k in ('date','open','high','low','close','volume')},'ma5':m5[i],'ma20':m20[i],'ma60':m60[i]})
        gl=gaps(rows); tl=trend(rows)
        payload={
            'schema_version':'5.4.42-technical-chart','generated_at':datetime.now(TZ).isoformat(),
            'code':x.get('code'),'name':x.get('name'),'market':x.get('market'),
            'record_count':len(candles),'first_date':candles[0]['date'],'last_date':candles[-1]['date'],
            'candles':candles,'gaps':gl,'trendlines':tl,'technical_summary':technical_summary(rows,m20,gl,tl)
        }
        (OUT/f"{x.get('code')}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8'); count+=1
    (OUT/'_status.json').write_text(json.dumps({'schema_version':'5.4.42-technical-chart','generated_at':datetime.now(TZ).isoformat(),'chart_count':count},ensure_ascii=False,indent=2),encoding='utf-8')
    print('technical charts',count)

if __name__=='__main__':main()
