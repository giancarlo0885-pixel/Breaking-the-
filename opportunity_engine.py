from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any

@dataclass
class RankedOpportunity:
    rank: int
    symbol: str
    action: str
    opportunity_score: float
    council_score: float
    confidence: float
    momentum: float
    risk_penalty: float
    reason: str

def _v(obj: Any, name: str, default=0.0):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)

def rank_opportunities(signals: list[Any], limit: int = 12) -> list[dict]:
    scored=[]
    for signal in signals:
        score=float(_v(signal,"score",0.5)); score=score*100 if score<=1 else score
        confidence=float(_v(signal,"confidence",0.5)); confidence=confidence*100 if confidence<=1 else confidence
        m5=float(_v(signal,"momentum_5d",0)); m20=float(_v(signal,"momentum_20d",0))
        vol=max(0.0,float(_v(signal,"volatility_20d",0)))
        volume=max(0.0,float(_v(signal,"volume_ratio",1)))
        risk=min(30.0,vol*18.0)
        opportunity=max(0.0,min(100.0, score*.52+confidence*.23+max(-15,min(15,(m5*.35+m20*.65)*100))+min(8,max(0,(volume-1)*5))-risk))
        scored.append((opportunity,signal,score,confidence,m5,m20,risk))
    scored.sort(key=lambda x:x[0], reverse=True)
    out=[]
    for rank,(opp,s,score,conf,m5,m20,risk) in enumerate(scored[:limit],1):
        out.append(asdict(RankedOpportunity(rank,str(_v(s,"symbol","")),str(_v(s,"action","HOLD")),round(opp,2),round(score,2),round(conf,2),round((m5+m20)/2*100,2),round(risk,2),str(_v(s,"reason","")))))
    return out
