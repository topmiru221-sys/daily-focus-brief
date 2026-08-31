from __future__ import annotations
import json, statistics
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
    def make(points, role):
        items=[]
        for a,b in zip(points[:-1],points[1:]):
            dx=b['index']-a['index']
            if dx<=0: continue
            slope=(b['price']-a['price'])/dx
            direction='ascending' if slope>0 else 'descending' if slope<0 else 'flat'
            items.append({'role':role,'direction':direction,'from':a,'to':b,'slope':round(slope,4),'strength':2,'label':f"{'上升' if direction=='ascending' else '下降' if direction=='descending' else '水平'}{'支撐' if role=='support' else '壓力'}"})
        return items[-4:]
    lines += make(lows,'support')
    lines += make(highs,'resistance')
    return lines[-8:]

def pct(a,b):
    if a is None or b in (None,0):return None
    return round((a-b)/b*100,2)

def decision_map():
    d=load(DECISION)
    return {str(x.get('code')):x for x in d.get('rankings',[]) if isinstance(x,dict) and x.get('code')}

def score_zone(center, touches, last_index, current_index, close, zone_type, source):
    distance_pct=abs(center-close)/close*100 if close else 999
    recency=max(0, 30-(current_index-last_index)) if current_index is not None and last_index is not None else 0
    proximity=max(0, 25-distance_pct*4)
    touch_score=min(35, touches*9)
    source_bonus=16 if source=='gap' else 8 if source=='ma' else 0
    base=touch_score+recency+proximity+source_bonus
    if zone_type=='support' and center>close: base-=8
    if zone_type=='resistance' and center<close: base-=8
    return max(1, round(base,1))

def cluster_levels(points, close, current_index):
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
        last=max(g,key=lambda x:x['index'])
        ztype='support' if center<=close else 'resistance'
        zones.append({'low':round(center-width,2),'high':round(center+width,2),'center':round(center,2),'touches':len(g),'last_date':last['date'],'last_index':last['index'],'type':ztype,'source':'pivot_cluster','strength_score':score_zone(center,len(g),last['index'],current_index,close,ztype,'pivot_cluster')})
    return zones

def zone(center, width_pct, kind, label, source):
    if not isinstance(center,(int,float)) or center<=0:return None
    return {'kind':kind,'label':label,'low':round(center*(1-width_pct),2),'high':round(center*(1+width_pct),2),'center':round(center,2),'source':source}

def select_zones(sr_zones, close):
    supports=[z for z in sr_zones if z['type']=='support']
    resistances=[z for z in sr_zones if z['type']=='resistance']
    supports.sort(key=lambda z:(-z['strength_score'], abs(close-z['center'])))
    resistances.sort(key=lambda z:(-z['strength_score'], abs(close-z['center'])))
    def fmt(z, idx, kind):
        return {**z, 'display_label': f"{'主要支撐' if kind=='support' and idx==0 else '次要支撐' if kind=='support' and idx==1 else '觀察支撐' if kind=='support' else '關鍵壓力' if idx==0 else '次要壓力' if idx==1 else '觀察壓力'}", 'rank': idx+1, 'distance_pct': round((close-z['center'])/z['center']*100,2) if kind=='support' else round((z['center']-close)/close*100,2), 'tested_recently': (z.get('last_index') is not None and z.get('last_index') >= 0)}
    return [fmt(z,i,'support') for i,z in enumerate(supports[:3])], [fmt(z,i,'resistance') for i,z in enumerate(resistances[:3])]

def decision_zones(dec, rows, ma20, sr_zones):
    if not dec:return []
    p=dec.get('trading_plan') or {}
    close=rows[-1]['close']; out=[]
    trigger=p.get('trigger'); invalid=p.get('invalidation'); target1=p.get('target1'); target2=p.get('target2')
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

def entry_hint(close, support_zones, resistance_zones, decision_zones):
    main_support=support_zones[0] if support_zones else None
    main_resistance=resistance_zones[0] if resistance_zones else None
    retest=next((z for z in decision_zones if z['kind']=='retest'),None)
    no_chase=next((z for z in decision_zones if z['kind']=='no_chase'),None)
    invalid=next((z for z in decision_zones if z['kind']=='invalidation'),None)
    if main_support and main_support['low'] <= close <= main_support['high']:
        return {'label':'接近主要支撐，可等回測反應','confidence':'high','reason':f"現價位於{main_support['display_label']}區內，近期測試 {main_support['touches']} 次。"}
    if retest and retest['low'] <= close <= retest['high']:
        return {'label':'位於回測區，可觀察止跌或量縮','confidence':'medium','reason':'現價進入預設回測區，適合等確認。'}
    if no_chase and close >= no_chase['low']:
        return {'label':'已進入不追價區，避免追高','confidence':'high','reason':'現價偏離均線／支撐過遠，上方風險報酬比下降。'}
    if invalid and close < invalid['high']:
        return {'label':'接近或跌入失效區，先控風險','confidence':'high','reason':'現價接近交易計畫失效區，應先觀察防守是否有效。'}
    if main_resistance and main_resistance['distance_pct'] is not None and main_resistance['distance_pct'] <= 3:
        return {'label':'接近關鍵壓力，突破前不宜積極追價','confidence':'medium','reason':'現價距離關鍵壓力很近，容易震盪。'}
    return {'label':'位置中性，等待更明確訊號','confidence':'low','reason':'目前不在最佳支撐／回測區，也未明確突破。'}

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
        sr=cluster_levels(pts, close, len(rows)-1)
        for g in gl:
            if g['status']!='filled':
                center=(g['low']+g['high'])/2
                ztype='support' if center<=close else 'resistance'
                sr.append({'low':g['low'],'high':g['high'],'center':round(center,2),'touches':1,'last_date':g['date'],'last_index':g['index'],'type':ztype,'source':'gap','strength_score':score_zone(center,1,g['index'],len(rows)-1,close,ztype,'gap')})
        for ma, label in ((m20[-1] if m20 else None,'ma20'), (m60[-1] if m60 else None,'ma60'), (m120[-1] if m120 else None,'ma120')):
            if isinstance(ma,(int,float)):
                ztype='support' if ma<=close else 'resistance'
                sr.append({'low':round(ma*0.994,2),'high':round(ma*1.006,2),'center':round(ma,2),'touches':1,'last_date':rows[-1]['date'],'last_index':len(rows)-1,'type':ztype,'source':'ma','strength_score':score_zone(ma,1,len(rows)-1,len(rows)-1,close,ztype,'ma')})
        dec=dm.get(str(x.get('code'))) or {}
        support_top, resistance_top = select_zones(sr, close)
        dz=decision_zones(dec,rows,m20,support_top+resistance_top)
        payload={
            'schema_version':'5.4.44-smart-zones',
            'generated_at':datetime.now(TZ).isoformat(),'code':x.get('code'),'name':x.get('name'),'market':x.get('market'),
            'record_count':len(candles),'first_date':candles[0]['date'],'last_date':candles[-1]['date'],
            'candles':candles,'gaps':gl,'trendlines':tl,
            'support_zones':support_top,'resistance_zones':resistance_top,'decision_zones':dz,
            'layer_defaults':{'candles':True,'volume':True,'ma5':False,'ma20':True,'ma60':True,'ma120':False,'trend_ascending':False,'trend_descending':False,'supports':True,'resistances':True,'gaps':False,'decision_zones':True,'targets':True},
            'entry_hint':entry_hint(close,support_top,resistance_top,dz),
            'decision_snapshot':{
               'score':dec.get('decision_score'),'grade':dec.get('grade'),'card_label':dec.get('card_label'),
               'action':(dec.get('trading_plan') or {}).get('action'),'trigger':(dec.get('trading_plan') or {}).get('trigger'),
               'invalidation':(dec.get('trading_plan') or {}).get('invalidation'),'target1':(dec.get('trading_plan') or {}).get('target1'),
               'target2':(dec.get('trading_plan') or {}).get('target2'),'risk_pct':(dec.get('trading_plan') or {}).get('risk_pct'),
               'rr1':(dec.get('trading_plan') or {}).get('rr1')
            }
        }
        (OUT/f"{x.get('code')}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');count+=1
    (OUT/'_status.json').write_text(json.dumps({'schema_version':'5.4.44-smart-zones','generated_at':datetime.now(TZ).isoformat(),'chart_count':count},ensure_ascii=False,indent=2),encoding='utf-8')
    print('technical charts',count)

if __name__=='__main__':main()
