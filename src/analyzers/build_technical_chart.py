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
    return (make(lows,'support')+make(highs,'resistance'))[-8:]

def decision_map():
    d=load(DECISION)
    return {str(x.get('code')):x for x in d.get('rankings',[]) if isinstance(x,dict) and x.get('code')}

def cluster_levels(points, close):
    if not points:return []
    tol=max(close*0.009,0.01)
    vals=sorted(points,key=lambda x:x['price'])
    groups=[]
    for p in vals:
        if not groups or abs(p['price']-statistics.mean(x['price'] for x in groups[-1]))>tol:
            groups.append([p])
        else:
            groups[-1].append(p)
    zones=[]
    for g in groups:
        center=statistics.mean(x['price'] for x in g)
        width=max(close*0.0045,(max(x['price'] for x in g)-min(x['price'] for x in g))/2+close*0.002)
        last=max(g,key=lambda x:x['index'])
        zones.append({
            'low':round(center-width,2),'high':round(center+width,2),'center':round(center,2),
            'touches':len(g),'last_date':last['date'],'last_index':last['index'],
            'type':'support' if center<=close else 'resistance',
            'source':'pivot_cluster'
        })
    return zones

def add_evidence(z, rows, close, mas):
    center=z['center']; width=max(z['high']-z['low'],close*0.008)
    # Re-test: candle range touched zone after initial pivot date, excluding last 2 bars.
    tests=0; held=0; last_test=None
    for i,r in enumerate(rows[:-2]):
        if r['low'] <= z['high'] and r['high'] >= z['low']:
            tests += 1; last_test=i
            if z['type']=='support' and r['close'] >= z['low']: held += 1
            if z['type']=='resistance' and r['close'] <= z['high']: held += 1
    ma_overlap=[name for name,val in mas.items() if isinstance(val,(int,float)) and z['low']-width*.5 <= val <= z['high']+width*.5]
    distance=abs(center-close)/close*100 if close else 999
    recency=(len(rows)-1-last_test) if last_test is not None else 999
    source_points=20 if z['source']=='pivot_cluster' else 14 if z['source']=='gap' else 0
    touch_points=min(36,tests*9)
    hold_points=min(18,held*6)
    recency_points=16 if recency<=10 else 10 if recency<=20 else 5 if recency<=40 else 0
    overlap_points=min(12,len(ma_overlap)*6)
    proximity=max(0,18-distance*2)
    score=round(source_points+touch_points+hold_points+recency_points+overlap_points+proximity,1)
    z.update({
        'tests':tests,'held_tests':held,'last_test_bars_ago':None if last_test is None else recency,
        'ma_overlap':ma_overlap,'distance_pct_abs':round(distance,2),'strength_score':score,
        'evidence_count':(1 if z['source'] in {'pivot_cluster','gap'} else 0)+(1 if tests>=2 else 0)+(1 if held>=1 else 0)+(1 if ma_overlap else 0)
    })
    return z

def valid_zone(z):
    d=z.get('distance_pct_abs',999)
    # Hard distance filter: operational zones only.
    if d>15:return False
    # MA-only zones are never enough by themselves.
    if z.get('source')=='ma':return False
    # Need structure + at least one actual historical reaction, or multiple touches.
    if z.get('evidence_count',0)<2:return False
    if z.get('tests',0)<2 and z.get('touches',0)<2:return False
    if z.get('strength_score',0)<38:return False
    return True

def select_zones(sr, close, kind):
    zs=[z for z in sr if z['type']==kind and valid_zone(z)]
    # Blend quality and proximity; prefer zones that matter now.
    zs.sort(key=lambda z:(-(z['strength_score']-z['distance_pct_abs']*1.5),z['distance_pct_abs']))
    labels_support=['主要支撐','次要支撐','觀察支撐']
    labels_resist=['關鍵壓力','次要壓力','觀察壓力']
    out=[]
    for i,z in enumerate(zs[:3]):
        q=dict(z)
        q['rank']=i+1
        q['display_label']=(labels_support if kind=='support' else labels_resist)[i]
        q['distance_pct']=round((close-q['center'])/q['center']*100,2) if kind=='support' else round((q['center']-close)/close*100,2)
        out.append(q)
    return out

def zone(center,width_pct,kind,label,source):
    if not isinstance(center,(int,float)) or center<=0:return None
    return {'kind':kind,'label':label,'low':round(center*(1-width_pct),2),'high':round(center*(1+width_pct),2),'center':round(center,2),'source':source}

def decision_zones(dec, rows, ma20, supports, resistances):
    if not dec:return []
    p=dec.get('trading_plan') or {};close=rows[-1]['close'];out=[]
    trigger=p.get('trigger');invalid=p.get('invalidation');target1=p.get('target1');target2=p.get('target2')
    nearest_sup=supports[0] if supports else None
    nearest_res=resistances[0] if resistances else None
    retest_center=trigger or (nearest_sup or {}).get('center') or (ma20[-1] if ma20 else None)
    z=zone(retest_center,0.012,'retest','回測區','decision.trigger/validated_support/ma20')
    if z:out.append(z)
    breakout_center=(nearest_res or {}).get('high') or trigger
    z=zone(breakout_center,0.008,'breakout','突破確認區','validated_resistance/trigger')
    if z:
        z['low']=round(z['center'],2);z['high']=round(z['center']*1.016,2);out.append(z)
    base=ma20[-1] if ma20 and ma20[-1] else close
    no_chase_low=max(base*1.08,(nearest_res or {}).get('center') or 0)
    if no_chase_low>0:
        out.append({'kind':'no_chase','label':'不追價區','low':round(no_chase_low,2),'high':round(max(no_chase_low*1.06,close*1.04),2),'center':round(no_chase_low,2),'source':'ma20_extension/resistance'})
    if isinstance(invalid,(int,float)) and invalid>0:
        out.append({'kind':'invalidation','label':'失效區','low':round(invalid*0.965,2),'high':round(invalid*1.005,2),'center':round(invalid,2),'source':'decision.invalidation'})
    for val,label in ((target1,'目標一'),(target2,'目標二')):
        if isinstance(val,(int,float)) and val>0:
            out.append({'kind':'target','label':label,'low':val,'high':val,'center':val,'source':'decision.target'})
    return out

def entry_hint(close, supports, resistances, dz):
    sup=supports[0] if supports else None;res=resistances[0] if resistances else None
    retest=next((z for z in dz if z['kind']=='retest'),None)
    no_chase=next((z for z in dz if z['kind']=='no_chase'),None)
    invalid=next((z for z in dz if z['kind']=='invalidation'),None)
    if no_chase and close>=no_chase['low']:
        return {'label':'已進入不追價區，避免追高','confidence':'high','reason':'現價偏離有效支撐／MA20 過遠，風險報酬比下降。'}
    if invalid and close<invalid['high']:
        return {'label':'接近或跌入失效區，先控風險','confidence':'high','reason':'現價接近交易計畫失效區。'}
    if sup and sup['low']<=close<=sup['high']:
        return {'label':'接近主要支撐，可等回測反應','confidence':'high','reason':f"主要支撐已測試 {sup['tests']} 次、守住 {sup['held_tests']} 次。"}
    if retest and retest['low']<=close<=retest['high']:
        return {'label':'位於回測區，可觀察止跌或量縮','confidence':'medium','reason':'現價進入回測區，等待價格確認。'}
    if res and res['distance_pct']<=3:
        return {'label':'接近關鍵壓力，突破前不宜積極追價','confidence':'medium','reason':'現價距有效壓力區低於 3%。'}
    if not supports:
        return {'label':'近期無有效支撐，不宜硬找進場點','confidence':'medium','reason':'15% 範圍內沒有通過回測／結構驗證的支撐區。'}
    return {'label':'位置中性，等待更明確訊號','confidence':'low','reason':'目前不在高品質回測區或突破確認區。'}

def main():
    OUT.mkdir(parents=True,exist_ok=True);dm=decision_map();count=0
    for p in HIST.glob('[0-9][0-9][0-9][0-9].json'):
        x=load(p)
        rows=[r for r in x.get('prices',[]) if all(isinstance(r.get(k),(int,float)) for k in ('open','high','low','close'))][-126:]
        if len(rows)<5:continue
        m5,m20,m60,m120=sma(rows,5),sma(rows,20),sma(rows,60),sma(rows,120)
        candles=[{**{k:r.get(k) for k in ('date','open','high','low','close','volume')},'ma5':m5[i],'ma20':m20[i],'ma60':m60[i],'ma120':m120[i]} for i,r in enumerate(rows)]
        close=rows[-1]['close'];gl=gaps(rows);tl=make_trendlines(rows)
        pts=pivots(rows,'low','low')[-20:]+pivots(rows,'high','high')[-20:]
        sr=cluster_levels(pts,close)
        for g in gl:
            if g['status']!='filled':
                center=(g['low']+g['high'])/2
                sr.append({'low':g['low'],'high':g['high'],'center':round(center,2),'touches':1,'last_date':g['date'],'last_index':g['index'],'type':'support' if center<=close else 'resistance','source':'gap'})
        mas={'MA20':m20[-1] if m20 else None,'MA60':m60[-1] if m60 else None,'MA120':m120[-1] if m120 else None}
        sr=[add_evidence(z,rows,close,mas) for z in sr]
        supports=select_zones(sr,close,'support');resistances=select_zones(sr,close,'resistance')
        dec=dm.get(str(x.get('code'))) or {}
        dz=decision_zones(dec,rows,m20,supports,resistances)
        payload={
          'schema_version':'5.4.44.1-validated-zones',
          'generated_at':datetime.now(TZ).isoformat(),'code':x.get('code'),'name':x.get('name'),'market':x.get('market'),
          'record_count':len(candles),'first_date':candles[0]['date'],'last_date':candles[-1]['date'],
          'candles':candles,'gaps':gl,'trendlines':tl,'support_zones':supports,'resistance_zones':resistances,'decision_zones':dz,
          'layer_defaults':{'candles':True,'volume':True,'ma5':False,'ma20':True,'ma60':True,'ma120':False,'trend_ascending':False,'trend_descending':False,'supports':True,'resistances':True,'gaps':False,'decision_zones':True,'targets':True},
          'entry_hint':entry_hint(close,supports,resistances,dz),
          'zone_methodology':{'max_distance_pct':15,'requires_structure':True,'requires_retest_or_multiple_touches':True,'ma_only_disallowed':True},
          'decision_snapshot':{
             'score':dec.get('decision_score'),'grade':dec.get('grade'),'card_label':dec.get('card_label'),
             'action':(dec.get('trading_plan') or {}).get('action'),'trigger':(dec.get('trading_plan') or {}).get('trigger'),
             'invalidation':(dec.get('trading_plan') or {}).get('invalidation'),'target1':(dec.get('trading_plan') or {}).get('target1'),
             'target2':(dec.get('trading_plan') or {}).get('target2'),'risk_pct':(dec.get('trading_plan') or {}).get('risk_pct'),
             'rr1':(dec.get('trading_plan') or {}).get('rr1')
          }
        }
        (OUT/f"{x.get('code')}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');count+=1
    (OUT/'_status.json').write_text(json.dumps({'schema_version':'5.4.44.1-validated-zones','generated_at':datetime.now(TZ).isoformat(),'chart_count':count},ensure_ascii=False,indent=2),encoding='utf-8')
    print('technical charts',count)

if __name__=='__main__':main()
