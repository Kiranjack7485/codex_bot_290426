from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class SetupType(str, Enum):
    LIQUIDITY_SWEEP_REVERSAL = "Liquidity Sweep Reversal"
    BREAK_AND_RETEST = "Break and Retest"
    TREND_PULLBACK = "Trend Pullback"


@dataclass(slots=True)
class LiquidityZone:
    label: str
    price: float
    kind: str


@dataclass(slots=True)
class FairValueGap:
    direction: Direction
    lower: float
    upper: float
    created_at: datetime


@dataclass(slots=True)
class SignalComponents:
    liquidity_sweep: bool
    market_structure_alignment: bool
    ema_alignment: bool
    volume_spike: bool

    @property
    def score(self) -> int:
        total = 0
        total += 3 if self.liquidity_sweep else 0
        total += 3 if self.market_structure_alignment else 0
        total += 2 if self.ema_alignment else 0
        total += 2 if self.volume_spike else 0
        return total


@dataclass(slots=True)
class TradeSignal:
    symbol: str
    direction: Direction
    setup: SetupType
    entry: float
    stop_loss: float
    take_profit: float
    rr_ratio: float
    score: int
    confidence_score: int
    timestamp: datetime
    components: SignalComponents
    liquidity_zone: LiquidityZone
    fair_value_gap: Optional[FairValueGap]
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PositionPlan:
    symbol: str
    direction: Direction
    entry: float
    stop_loss: float
    take_profit: float
    quantity: float
    leverage: int
    notional_value: float
    margin_required: float
    risk_amount: float
    rr_ratio: float
    score: int
    setup: SetupType
    entry_order_type: str


@dataclass(slots=True)
class ActiveTrade:
    symbol: str
    direction: Direction
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    score: int
    setup: Optional[SetupType]
    opened_at: datetime
    order_ids: Dict[str, Any] = field(default_factory=dict)
