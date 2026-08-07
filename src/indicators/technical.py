from __future__ import annotations
from math import sqrt
from statistics import mean, pstdev
from typing import Any


def num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct(current: float | None, reference: float | None) -> float | None:
    if current is None or reference in (None, 0):
        return None
    return (current / reference - 1) * 100


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return mean(values[-period:])


def ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    out = [values[0]]
    for value in values[1:]:
        out.append(alpha * value + (1 - alpha) * out[-1])
    return out


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains, losses = [], []
    for a, b in zip(values[-(period + 1):-1], values[-period:]):
        change = b - a
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def true_ranges(rows: list[dict[str, Any]]) -> list[float]:
    out = []
    previous_close = None
    for row in rows:
        high, low, close = num(row.get("high")), num(row.get("low")), num(row.get("close"))
        if high is None or low is None or close is None:
            previous_close = close if close is not None else previous_close
            continue
        if previous_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - previous_close), abs(low - previous_close))
        out.append(tr)
        previous_close = close
    return out


def atr(rows: list[dict[str, Any]], period: int = 14) -> float | None:
    trs = true_ranges(rows)
    return mean(trs[-period:]) if len(trs) >= period else None


def macd(values: list[float]) -> dict[str, float | None]:
    if len(values) < 26:
        return {"macd": None, "signal": None, "histogram": None}
    fast = ema_series(values, 12)
    slow = ema_series(values, 26)
    line = [a - b for a, b in zip(fast, slow)]
    signal = ema_series(line, 9)
    return {
        "macd": line[-1],
        "signal": signal[-1],
        "histogram": line[-1] - signal[-1],
    }


def stochastic(rows: list[dict[str, Any]], period: int = 9) -> dict[str, float | None]:
    if len(rows) < period:
        return {"k": None, "d": None}
    raw_k = []
    start = max(0, len(rows) - period - 2)
    for i in range(start + period - 1, len(rows)):
        window = rows[i - period + 1:i + 1]
        highs = [num(r.get("high")) for r in window]
        lows = [num(r.get("low")) for r in window]
        close = num(rows[i].get("close"))
        highs = [x for x in highs if x is not None]
        lows = [x for x in lows if x is not None]
        if not highs or not lows or close is None or max(highs) == min(lows):
            continue
        raw_k.append((close - min(lows)) / (max(highs) - min(lows)) * 100)
    if not raw_k:
        return {"k": None, "d": None}
    k = raw_k[-1]
    d = mean(raw_k[-3:]) if len(raw_k) >= 3 else mean(raw_k)
    return {"k": k, "d": d}


def bollinger(values: list[float], period: int = 20, std_mult: float = 2.0) -> dict[str, float | None]:
    if len(values) < period:
        return {"upper": None, "middle": None, "lower": None, "bandwidth_pct": None}
    window = values[-period:]
    middle = mean(window)
    std = pstdev(window)
    upper = middle + std_mult * std
    lower = middle - std_mult * std
    bandwidth = (upper - lower) / middle * 100 if middle else None
    return {"upper": upper, "middle": middle, "lower": lower, "bandwidth_pct": bandwidth}


def local_levels(rows: list[dict[str, Any]], periods=(20, 60)) -> tuple[list[dict], list[dict]]:
    if not rows:
        return [], []
    close = num(rows[-1].get("close"))
    supports, resistances = [], []
    for period in periods:
        window = rows[-period:] if len(rows) >= period else rows
        highs = [num(r.get("high")) for r in window]
        lows = [num(r.get("low")) for r in window]
        highs = [x for x in highs if x is not None]
        lows = [x for x in lows if x is not None]
        if not highs or not lows or close is None:
            continue
        low, high = min(lows), max(highs)
        if low < close:
            supports.append({"label": f"近{period}日低點", "price": round(low,2), "distance_pct": round(pct(low,close),2)})
        if high > close:
            resistances.append({"label": f"近{period}日高點", "price": round(high,2), "upside_pct": round(pct(high,close),2)})
    return supports, resistances


def trend_state(close, ma5, ma10, ma20, ma60, ma120) -> str:
    if close is None:
        return "資料不足"
    if ma20 and ma60 and close > ma20 > ma60:
        if ma5 and ma10 and ma5 > ma10 > ma20:
            return "多頭排列"
        return "多頭趨勢"
    if ma20 and ma60 and close < ma20 < ma60:
        return "空頭趨勢"
    if ma20 and close > ma20:
        return "偏多整理"
    if ma20 and close < ma20:
        return "偏弱整理"
    return "資料不足"


def position_state(close, ma20, ma60, rsi14, bb_upper, bb_lower) -> str:
    if close is None:
        return "資料不足"
    d20 = pct(close, ma20)
    if d20 is not None and d20 >= 15:
        return "高乖離／追價風險"
    if rsi14 is not None and rsi14 >= 75:
        return "短線過熱"
    if bb_upper is not None and close >= bb_upper:
        return "接近布林上緣"
    if d20 is not None and -3 <= d20 <= 5:
        return "靠近20MA／可觀察"
    if ma60 is not None and close < ma60:
        return "60MA下方／偏弱"
    if bb_lower is not None and close <= bb_lower:
        return "布林下緣／超跌觀察"
    return "中性位置"


def calculate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [r for r in rows if isinstance(r,dict) and num(r.get("close")) is not None]
    if not rows:
        return {"status":"missing","record_count":0,"price_date":None}

    closes=[num(r.get("close")) for r in rows]
    volumes=[num(r.get("volume")) for r in rows]
    closes=[x for x in closes if x is not None]
    latest=rows[-1]
    close=num(latest.get("close"))
    ma={p:sma(closes,p) for p in (5,10,20,60,120,240)}
    vol_clean=[x for x in volumes if x is not None]
    volume=num(latest.get("volume"))
    vol20=sma(vol_clean,20)
    vol60=sma(vol_clean,60)
    rsi14=rsi(closes,14)
    atr14=atr(rows,14)
    m=macd(closes)
    kd=stochastic(rows,9)
    bb=bollinger(closes,20,2)

    supports,resistances=local_levels(rows,(20,60))
    for p in (20,60,120):
        value=ma[p]
        if value is not None and close is not None and value < close:
            supports.append({"label":f"{p}日均線","price":round(value,2),"distance_pct":round(pct(value,close),2)})
        if value is not None and close is not None and value > close:
            resistances.append({"label":f"{p}日均線","price":round(value,2),"upside_pct":round(pct(value,close),2)})
    supports=sorted({(x["label"],x["price"]):x for x in supports}.values(),key=lambda x:x["price"],reverse=True)
    resistances=sorted({(x["label"],x["price"]):x for x in resistances}.values(),key=lambda x:x["price"])

    nearest_support=supports[0]["price"] if supports else None
    invalidation=(nearest_support - 0.5*atr14) if nearest_support is not None and atr14 is not None else (nearest_support*0.985 if nearest_support else None)
    target1=resistances[0]["price"] if resistances else None
    target2=resistances[1]["price"] if len(resistances)>1 else None

    def rr(stop,target):
        if None in (close,stop,target) or close<=stop or target<=close:return None
        return (target-close)/(close-stop)

    risk_pct=(close-invalidation)/close*100 if close and invalidation and invalidation<close else None
    reward1=(target1-close)/close*100 if close and target1 and target1>close else None
    reward2=(target2-close)/close*100 if close and target2 and target2>close else None

    trend=trend_state(close,ma[5],ma[10],ma[20],ma[60],ma[120])
    position=position_state(close,ma[20],ma[60],rsi14,bb["upper"],bb["lower"])

    return {
        "status":"ok","record_count":len(rows),"price_date":latest.get("date"),"close":round(close,2),
        "ma5":round(ma[5],2) if ma[5] is not None else None,
        "ma10":round(ma[10],2) if ma[10] is not None else None,
        "ma20":round(ma[20],2) if ma[20] is not None else None,
        "ma60":round(ma[60],2) if ma[60] is not None else None,
        "ma120":round(ma[120],2) if ma[120] is not None else None,
        "ma240":round(ma[240],2) if ma[240] is not None else None,
        "distance_ma20_pct":round(pct(close,ma[20]),2) if ma[20] else None,
        "distance_ma60_pct":round(pct(close,ma[60]),2) if ma[60] else None,
        "volume":volume,
        "avg_volume20":round(vol20,2) if vol20 is not None else None,
        "avg_volume60":round(vol60,2) if vol60 is not None else None,
        "volume_ratio20":round(volume/vol20,2) if volume and vol20 else None,
        "volume_ratio60":round(volume/vol60,2) if volume and vol60 else None,
        "rsi14":round(rsi14,2) if rsi14 is not None else None,
        "atr14":round(atr14,2) if atr14 is not None else None,
        "atr_pct":round(atr14/close*100,2) if atr14 and close else None,
        "macd":round(m["macd"],3) if m["macd"] is not None else None,
        "macd_signal":round(m["signal"],3) if m["signal"] is not None else None,
        "macd_histogram":round(m["histogram"],3) if m["histogram"] is not None else None,
        "kd_k":round(kd["k"],2) if kd["k"] is not None else None,
        "kd_d":round(kd["d"],2) if kd["d"] is not None else None,
        "bollinger_upper":round(bb["upper"],2) if bb["upper"] is not None else None,
        "bollinger_middle":round(bb["middle"],2) if bb["middle"] is not None else None,
        "bollinger_lower":round(bb["lower"],2) if bb["lower"] is not None else None,
        "bollinger_bandwidth_pct":round(bb["bandwidth_pct"],2) if bb["bandwidth_pct"] is not None else None,
        "trend":trend,"position":position,
        "supports":supports[:4],"resistances":resistances[:4],
        "suggested_stop":round(invalidation,2) if invalidation is not None else None,
        "invalidation":round(invalidation,2) if invalidation is not None else None,
        "target1":target1,"target2":target2,
        "risk_pct":round(risk_pct,2) if risk_pct is not None else None,
        "reward1_pct":round(reward1,2) if reward1 is not None else None,
        "reward2_pct":round(reward2,2) if reward2 is not None else None,
        "rr1":round(rr(invalidation,target1),2) if rr(invalidation,target1) is not None else None,
        "rr2":round(rr(invalidation,target2),2) if rr(invalidation,target2) is not None else None,
    }
