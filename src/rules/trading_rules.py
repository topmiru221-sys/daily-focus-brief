from __future__ import annotations
from typing import Any


def evaluate(technical: dict[str, Any]) -> dict[str, Any]:
    reasons, flags = [], []
    score = 50.0

    if technical.get("status") != "ok":
        return {
            "technical_score":30.0,
            "risk_quality_score":25.0,
            "reasons":["歷史行情不足"],
            "risk_flags":["尚未完成歷史行情回補"],
            "trading_plan":{"action":"資料不足","trigger":None,"invalidation":None,"target1":None,"target2":None},
        }

    trend=technical.get("trend")
    position=technical.get("position")
    d20=technical.get("distance_ma20_pct")
    d60=technical.get("distance_ma60_pct")
    vr=technical.get("volume_ratio20")
    rsi=technical.get("rsi14")
    macdh=technical.get("macd_histogram")
    risk=technical.get("risk_pct")
    rr1=technical.get("rr1")

    if trend=="多頭排列":
        score+=20;reasons.append("5/10/20MA 多頭排列")
    elif trend=="多頭趨勢":
        score+=14;reasons.append("價格位於20MA與60MA之上")
    elif trend=="偏多整理":
        score+=7;reasons.append("價格仍守在20MA之上")
    elif trend in {"空頭趨勢","偏弱整理"}:
        score-=18;flags.append("技術趨勢偏弱")

    if d20 is not None:
        if 0 <= d20 <= 6:
            score+=10;reasons.append(f"距20MA僅 {d20:.2f}%")
        elif d20 >= 15:
            score-=14;flags.append(f"距20MA達 {d20:.2f}%，追價風險偏高")
        elif d20 < -5:
            score-=10;flags.append("跌破20MA且乖離擴大")

    if d60 is not None and d60 >= 0:
        score+=6;reasons.append("站上60MA")

    if vr is not None:
        if 1.2 <= vr <= 2.5:
            score+=7;reasons.append(f"量能為20日均量 {vr:.2f} 倍")
        elif vr > 3:
            flags.append("量能過度放大，短線波動風險提高")

    if rsi is not None:
        if 50 <= rsi <= 68:
            score+=5;reasons.append(f"RSI14 {rsi:.1f}，動能健康")
        elif rsi >= 75:
            score-=7;flags.append(f"RSI14 {rsi:.1f}，短線過熱")
        elif rsi < 40:
            score-=5;flags.append("RSI 動能偏弱")

    if macdh is not None:
        if macdh > 0:
            score+=5;reasons.append("MACD柱狀體為正")
        else:
            score-=3

    score=max(0,min(100,score))

    rq=50.0
    if risk is not None:
        rq += 25 if risk <= 5 else 12 if risk <= 8 else -18 if risk >= 12 else 0
    if rr1 is not None:
        rq += 25 if rr1 >= 2 else 10 if rr1 >= 1.3 else -25
        if rr1 < 1.3:
            flags.append(f"第一目標 R/R 僅 {rr1:.2f}")
    else:
        rq-=10
    rq=max(0,min(100,rq))

    stop=technical.get("invalidation") or technical.get("suggested_stop")
    target1=technical.get("target1")
    target2=technical.get("target2")
    ma20=technical.get("ma20")

    if risk is None or stop is None:
        action="等待資料完整"
        trigger=None
    elif position in {"高乖離／追價風險","短線過熱"}:
        action="等待拉回，不追價"
        trigger=ma20
    elif rr1 is not None and rr1 >= 2 and risk <= 6 and trend in {"多頭排列","多頭趨勢","偏多整理"}:
        action="可建立交易計畫"
        trigger=technical.get("close")
    elif trend in {"多頭排列","多頭趨勢","偏多整理"}:
        action="等待回測支撐"
        trigger=ma20 or (technical.get("supports") or [{}])[0].get("price")
    else:
        action="觀察，暫不建立部位"
        trigger=None

    return {
        "technical_score":round(score,1),
        "risk_quality_score":round(rq,1),
        "reasons":reasons,
        "risk_flags":flags,
        "trading_plan":{
            "action":action,
            "trigger":round(trigger,2) if isinstance(trigger,(int,float)) else trigger,
            "invalidation":stop,
            "target1":target1,
            "target2":target2,
            "risk_pct":risk,
            "rr1":rr1,
            "position":position,
            "trend":trend,
        }
    }
