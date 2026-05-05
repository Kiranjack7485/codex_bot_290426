from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MarketType(str, Enum):
    CRYPTO = "CRYPTO"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class CryptoSetup(str, Enum):
    LIQUIDITY_SWEEP_REVERSAL = "Liquidity Sweep Reversal"
    BREAK_AND_RETEST = "Break and Retest"
    TREND_PULLBACK = "Trend Pullback"


class CryptoSession(str, Enum):
    INDIA_CRYPTO = "INDIA_CRYPTO"
    OVERLAP = "US_LONDON_OVERLAP"


@dataclass(frozen=True, slots=True)
class LiquidityZone:
    label: str
    price: float
    kind: str


@dataclass(frozen=True, slots=True)
class FairValueGap:
    direction: Direction
    lower: float
    upper: float
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CryptoSignalComponents:
    liquidity_sweep: bool = False
    market_structure_alignment: bool = False
    ema_alignment: bool = False
    volume_spike: bool = False

    @property
    def score(self) -> int:
        total = 0
        total += 3 if self.liquidity_sweep else 0
        total += 3 if self.market_structure_alignment else 0
        total += 2 if self.ema_alignment else 0
        total += 2 if self.volume_spike else 0
        return total


@dataclass(frozen=True, slots=True)
class CryptoSignal:
    market: MarketType
    symbol: str
    direction: Direction
    setup: CryptoSetup
    entry_zone: tuple[float, float]
    stop_loss: float
    take_profit: float
    rr_ratio: float
    score: int
    confidence_score: int
    timestamp: datetime
    liquidity_zone: LiquidityZone
    fair_value_gap: Optional[FairValueGap]
    components: CryptoSignalComponents
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReversalAlert:
    market: MarketType
    symbol: str
    previous_direction: Direction
    new_direction: Direction
    timestamp: datetime
    reasons: List[str]
    suggested_action: str
    confidence_score: int


Signal = CryptoSignal
