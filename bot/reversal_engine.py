from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

from bot.models import CryptoSignal, Direction, MarketType, ReversalAlert
from bot.strategy_engine import CryptoStrategyEngine


@dataclass(slots=True)
class TrackedSignalState:
    signal: CryptoSignal
    reversal_sent: bool = False


class ReversalEngine:
    def __init__(self, crypto_strategy: CryptoStrategyEngine) -> None:
        self.crypto_strategy = crypto_strategy
        self.tracked: Dict[str, TrackedSignalState] = {}

    def track(self, signal: CryptoSignal) -> None:
        self.tracked[f"CRYPTO:{signal.symbol}"] = TrackedSignalState(signal=signal, reversal_sent=False)

    def clear_all(self) -> None:
        self.tracked = {}

    def crypto_reversal(self, symbol: str, primary_frame: pd.DataFrame) -> Optional[ReversalAlert]:
        state = self.tracked.get(f"CRYPTO:{symbol}")
        if state is None or state.reversal_sent:
            return None
        frame = self.crypto_strategy.prepare_reversal_frame(primary_frame)
        if len(frame) < 8:
            return None
        previous_signal = state.signal
        latest = frame.iloc[-1]
        prior = frame.iloc[-2]
        current_structure = self._simple_structure_bias(frame)
        if current_structure is None or current_structure == previous_signal.direction:
            return None
        strong_reversal_candle = bool(
            latest["body_ratio"] >= 0.60
            and latest["total_wick_ratio"] <= 0.40
            and ((latest["close"] > latest["open"]) if current_structure == Direction.LONG else (latest["close"] < latest["open"]))
        )
        volume_spike = bool(latest["volume"] > latest["volume_ma"] * 1.2)
        ema_cross = self._ema_cross_against(previous_signal.direction, prior, latest)
        if not (strong_reversal_candle and volume_spike and ema_cross):
            return None
        state.reversal_sent = True
        return ReversalAlert(
            market=MarketType.CRYPTO,
            symbol=symbol,
            previous_direction=previous_signal.direction,
            new_direction=current_structure,
            timestamp=latest["timestamp"].to_pydatetime(),
            reasons=[
                "Opposite market structure formation confirmed",
                "Strong reversal candle on close",
                "Volume spike in opposite direction",
                "EMA 9/21 crossover against prior direction",
            ],
            suggested_action="Partial profit booking or full exit",
            confidence_score=9,
        )

    @staticmethod
    def _simple_structure_bias(frame: pd.DataFrame) -> Optional[Direction]:
        recent = frame.tail(6)
        if len(recent) < 6:
            return None
        last_high = float(recent["high"].iloc[-1])
        prev_high = float(recent["high"].iloc[-3])
        last_low = float(recent["low"].iloc[-1])
        prev_low = float(recent["low"].iloc[-3])
        if last_high > prev_high and last_low > prev_low:
            return Direction.LONG
        if last_high < prev_high and last_low < prev_low:
            return Direction.SHORT
        return None

    @staticmethod
    def _ema_cross_against(previous_direction: Direction, prior: pd.Series, latest: pd.Series) -> bool:
        if previous_direction == Direction.LONG:
            return bool(prior["ema_9"] >= prior["ema_21"] and latest["ema_9"] < latest["ema_21"])
        return bool(prior["ema_9"] <= prior["ema_21"] and latest["ema_9"] > latest["ema_21"])
