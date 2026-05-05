from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd
from ta.trend import EMAIndicator

from bot.config import CryptoConfig
from bot.models import CryptoSetup, CryptoSignal, CryptoSignalComponents, Direction, FairValueGap, LiquidityZone, MarketType


@dataclass(slots=True)
class StructureState:
    bias: Optional[Direction]
    swing_highs: Sequence[Tuple[pd.Timestamp, float]]
    swing_lows: Sequence[Tuple[pd.Timestamp, float]]


class CryptoStrategyEngine:
    def __init__(self, config: CryptoConfig) -> None:
        self.config = config
        self.emitted: Set[str] = set()

    def evaluate(self, symbol: str, primary: pd.DataFrame, confirmation: pd.DataFrame) -> Optional[CryptoSignal]:
        primary = self._prepare_frame(primary.copy())
        confirmation = self._prepare_frame(confirmation.copy())
        if primary.empty or confirmation.empty:
            return None

        primary_structure = self._detect_market_structure(primary)
        confirmation_structure = self._detect_market_structure(confirmation)
        if primary_structure.bias is None or confirmation_structure.bias is None:
            return None
        if primary_structure.bias != confirmation_structure.bias:
            return None

        latest = primary.iloc[-1]
        ema_direction = self._ema_direction(latest)
        if ema_direction is None or ema_direction != primary_structure.bias:
            return None

        volume_spike = bool(latest["volume"] >= latest["volume_ma"] * self.config.volume_spike_factor)
        if not volume_spike:
            return None

        liquidity_zones = self._build_liquidity_zones(primary, primary_structure)
        if not liquidity_zones:
            return None

        fvg = self._find_relevant_fvg(primary, primary_structure.bias, float(latest["close"]))
        signal = self._detect_liquidity_sweep_reversal(symbol, primary, primary_structure, liquidity_zones, fvg, volume_spike, ema_direction)
        if signal is None:
            signal = self._detect_break_and_retest(symbol, primary, primary_structure, liquidity_zones, fvg, volume_spike, ema_direction)
        if signal is None:
            signal = self._detect_trend_pullback(symbol, primary, primary_structure, liquidity_zones, fvg, volume_spike, ema_direction)
        if signal is None:
            return None

        key = f"{signal.symbol}:{signal.direction.value}:{signal.setup.value}:{signal.timestamp.isoformat()}"
        if key in self.emitted:
            return None
        self.emitted.add(key)
        return signal

    def prepare_reversal_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        return self._prepare_frame(frame.copy())

    def _prepare_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        frame["ema_9"] = EMAIndicator(close=frame["close"], window=9).ema_indicator()
        frame["ema_21"] = EMAIndicator(close=frame["close"], window=21).ema_indicator()
        frame["volume_ma"] = frame["volume"].rolling(self.config.volume_ma_period).mean()
        price_range = (frame["high"] - frame["low"]).replace(0, pd.NA)
        frame["body_ratio"] = (frame["close"] - frame["open"]).abs() / price_range
        frame["total_wick_ratio"] = 1 - frame["body_ratio"]
        return frame.dropna().reset_index(drop=True)

    def _detect_market_structure(self, frame: pd.DataFrame) -> StructureState:
        swing_highs, swing_lows = self._extract_swings(frame)
        highs = list(swing_highs)[-self.config.structure_swings :]
        lows = list(swing_lows)[-self.config.structure_swings :]
        if len(highs) < 2 or len(lows) < 2:
            return StructureState(None, highs, lows)
        bullish = highs[-1][1] > highs[-2][1] and lows[-1][1] > lows[-2][1]
        bearish = highs[-1][1] < highs[-2][1] and lows[-1][1] < lows[-2][1]
        if bullish and not bearish:
            return StructureState(Direction.LONG, highs, lows)
        if bearish and not bullish:
            return StructureState(Direction.SHORT, highs, lows)
        return StructureState(None, highs, lows)

    def _extract_swings(self, frame: pd.DataFrame) -> Tuple[List[Tuple[pd.Timestamp, float]], List[Tuple[pd.Timestamp, float]]]:
        highs: List[Tuple[pd.Timestamp, float]] = []
        lows: List[Tuple[pd.Timestamp, float]] = []
        lookback = self.config.swing_lookback
        for idx in range(lookback, len(frame) - lookback):
            high = frame.loc[idx, "high"]
            low = frame.loc[idx, "low"]
            if high == frame.loc[idx - lookback : idx + lookback, "high"].max():
                highs.append((frame.loc[idx, "timestamp"], float(high)))
            if low == frame.loc[idx - lookback : idx + lookback, "low"].min():
                lows.append((frame.loc[idx, "timestamp"], float(low)))
        return highs, lows

    def _build_liquidity_zones(self, frame: pd.DataFrame, structure: StructureState) -> List[LiquidityZone]:
        latest_day = frame["timestamp"].dt.date.iloc[-1]
        intraday = frame[frame["timestamp"].dt.date == latest_day]
        zones: List[LiquidityZone] = []
        if structure.swing_highs:
            zones.append(LiquidityZone("Previous Swing High", structure.swing_highs[-1][1], "swing_high"))
        if structure.swing_lows:
            zones.append(LiquidityZone("Previous Swing Low", structure.swing_lows[-1][1], "swing_low"))
        zones.append(LiquidityZone("Session High", float(intraday["high"].max()), "session_high"))
        zones.append(LiquidityZone("Session Low", float(intraday["low"].min()), "session_low"))
        zones.extend(self._equal_levels(frame))
        return zones

    def _equal_levels(self, frame: pd.DataFrame) -> List[LiquidityZone]:
        swing_highs, swing_lows = self._extract_swings(frame)
        tolerance = self.config.equal_level_tolerance_bps / 10_000
        zones: List[LiquidityZone] = []
        for first, second in zip(swing_highs[-6:], swing_highs[-5:]):
            if abs(first[1] - second[1]) / second[1] <= tolerance:
                zones.append(LiquidityZone("Equal Highs", float(np.mean([first[1], second[1]])), "equal_highs"))
        for first, second in zip(swing_lows[-6:], swing_lows[-5:]):
            if abs(first[1] - second[1]) / second[1] <= tolerance:
                zones.append(LiquidityZone("Equal Lows", float(np.mean([first[1], second[1]])), "equal_lows"))
        return zones

    def _find_relevant_fvg(self, frame: pd.DataFrame, direction: Direction, current_price: float) -> Optional[FairValueGap]:
        gaps: List[FairValueGap] = []
        for idx in range(2, len(frame)):
            first = frame.iloc[idx - 2]
            third = frame.iloc[idx]
            if third["low"] > first["high"]:
                gaps.append(FairValueGap(Direction.LONG, float(first["high"]), float(third["low"]), third["timestamp"].to_pydatetime()))
            if third["high"] < first["low"]:
                gaps.append(FairValueGap(Direction.SHORT, float(third["high"]), float(first["low"]), third["timestamp"].to_pydatetime()))
        tolerance = current_price * (self.config.fvg_fill_tolerance_bps / 10_000)
        direction_gaps = [gap for gap in gaps if gap.direction == direction]
        aligned = [gap for gap in direction_gaps if gap.lower - tolerance <= current_price <= gap.upper + tolerance]
        return aligned[-1] if aligned else (direction_gaps[-1] if direction_gaps else None)

    def _detect_liquidity_sweep_reversal(self, symbol: str, frame: pd.DataFrame, structure: StructureState, zones: List[LiquidityZone], fvg: Optional[FairValueGap], volume_spike: bool, ema_direction: Direction) -> Optional[CryptoSignal]:
        latest = frame.iloc[-1]
        previous = frame.iloc[-2]
        for zone in zones:
            if structure.bias == Direction.LONG:
                sweep = latest["low"] < zone.price and latest["close"] > zone.price and latest["close"] > latest["open"]
                if sweep and fvg and fvg.direction == Direction.LONG:
                    return self._build_signal(symbol, Direction.LONG, CryptoSetup.LIQUIDITY_SWEEP_REVERSAL, latest, zone, fvg, True, volume_spike, ema_direction, structure.bias, min(float(latest["low"]), float(previous["low"])), float(latest["close"]))
            if structure.bias == Direction.SHORT:
                sweep = latest["high"] > zone.price and latest["close"] < zone.price and latest["close"] < latest["open"]
                if sweep and fvg and fvg.direction == Direction.SHORT:
                    return self._build_signal(symbol, Direction.SHORT, CryptoSetup.LIQUIDITY_SWEEP_REVERSAL, latest, zone, fvg, True, volume_spike, ema_direction, structure.bias, float(latest["close"]), max(float(latest["high"]), float(previous["high"])))
        return None

    def _detect_break_and_retest(self, symbol: str, frame: pd.DataFrame, structure: StructureState, zones: List[LiquidityZone], fvg: Optional[FairValueGap], volume_spike: bool, ema_direction: Direction) -> Optional[CryptoSignal]:
        latest = frame.iloc[-1]
        previous = frame.iloc[-2]
        tolerance = float(latest["close"]) * (self.config.break_retest_tolerance_bps / 10_000)
        for zone in zones:
            if structure.bias == Direction.LONG:
                if previous["close"] > zone.price and latest["low"] <= zone.price + tolerance and latest["close"] > zone.price and fvg and fvg.direction == Direction.LONG:
                    return self._build_signal(symbol, Direction.LONG, CryptoSetup.BREAK_AND_RETEST, latest, zone, fvg, False, volume_spike, ema_direction, structure.bias, min(float(latest["low"]), zone.price), float(latest["close"]))
            if structure.bias == Direction.SHORT:
                if previous["close"] < zone.price and latest["high"] >= zone.price - tolerance and latest["close"] < zone.price and fvg and fvg.direction == Direction.SHORT:
                    return self._build_signal(symbol, Direction.SHORT, CryptoSetup.BREAK_AND_RETEST, latest, zone, fvg, False, volume_spike, ema_direction, structure.bias, float(latest["close"]), max(float(latest["high"]), zone.price))
        return None

    def _detect_trend_pullback(self, symbol: str, frame: pd.DataFrame, structure: StructureState, zones: List[LiquidityZone], fvg: Optional[FairValueGap], volume_spike: bool, ema_direction: Direction) -> Optional[CryptoSignal]:
        latest = frame.iloc[-1]
        tolerance = float(latest["close"]) * (self.config.pullback_ema_tolerance_bps / 10_000)
        relevant_zone = self._nearest_zone(float(latest["close"]), zones, structure.bias)
        if relevant_zone is None or fvg is None or fvg.direction != structure.bias:
            return None
        if structure.bias == Direction.LONG:
            touched_ema = latest["low"] <= latest["ema_9"] + tolerance or latest["low"] <= latest["ema_21"] + tolerance
            zone_respected = latest["low"] <= relevant_zone.price + tolerance and latest["close"] > relevant_zone.price
            if touched_ema and zone_respected:
                return self._build_signal(symbol, Direction.LONG, CryptoSetup.TREND_PULLBACK, latest, relevant_zone, fvg, False, volume_spike, ema_direction, structure.bias, min(float(latest["low"]), float(latest["ema_21"])), float(latest["close"]))
        if structure.bias == Direction.SHORT:
            touched_ema = latest["high"] >= latest["ema_9"] - tolerance or latest["high"] >= latest["ema_21"] - tolerance
            zone_respected = latest["high"] >= relevant_zone.price - tolerance and latest["close"] < relevant_zone.price
            if touched_ema and zone_respected:
                return self._build_signal(symbol, Direction.SHORT, CryptoSetup.TREND_PULLBACK, latest, relevant_zone, fvg, False, volume_spike, ema_direction, structure.bias, float(latest["close"]), max(float(latest["high"]), float(latest["ema_21"])))
        return None

    def _build_signal(self, symbol: str, direction: Direction, setup: CryptoSetup, latest: pd.Series, zone: LiquidityZone, fvg: Optional[FairValueGap], liquidity_sweep: bool, volume_spike: bool, ema_direction: Direction, structure_bias: Direction, anchor_low: float, anchor_high: float) -> Optional[CryptoSignal]:
        components = CryptoSignalComponents(
            liquidity_sweep=liquidity_sweep,
            market_structure_alignment=structure_bias == direction,
            ema_alignment=ema_direction == direction,
            volume_spike=volume_spike,
        )
        score = components.score
        if score < self.config.min_signal_score:
            return None
        entry = float(latest["close"])
        if direction == Direction.LONG:
            stop_loss = anchor_low
            risk = entry - stop_loss
            if risk <= 0:
                return None
            take_profit = entry + risk * (2.0 if setup == CryptoSetup.LIQUIDITY_SWEEP_REVERSAL else 1.5)
        else:
            stop_loss = anchor_high
            risk = stop_loss - entry
            if risk <= 0:
                return None
            take_profit = entry - risk * (2.0 if setup == CryptoSetup.LIQUIDITY_SWEEP_REVERSAL else 1.5)
        rr_ratio = abs((take_profit - entry) / (entry - stop_loss))
        entry_buffer = abs(entry - stop_loss) * 0.15
        reasons = [
            f"Setup: {setup.value}",
            f"Liquidity zone: {zone.label} at {zone.price:.6f}",
            "Market structure aligned on 5m and 15m",
            "EMA 9/21 aligned with direction",
            "Volume spike confirmed",
        ]
        if fvg:
            reasons.append(f"FVG aligned between {fvg.lower:.6f} and {fvg.upper:.6f}")
        if liquidity_sweep:
            reasons.append("Liquidity sweep confirmed before entry")
        return CryptoSignal(
            market=MarketType.CRYPTO,
            symbol=symbol,
            direction=direction,
            setup=setup,
            entry_zone=(entry - entry_buffer, entry + entry_buffer),
            stop_loss=stop_loss,
            take_profit=take_profit,
            rr_ratio=rr_ratio,
            score=score,
            confidence_score=score,
            timestamp=latest["timestamp"].to_pydatetime(),
            liquidity_zone=zone,
            fair_value_gap=fvg,
            components=components,
            reasons=reasons,
            metadata={"ema_9": float(latest["ema_9"]), "ema_21": float(latest["ema_21"]), "volume_ma": float(latest["volume_ma"])},
        )

    @staticmethod
    def _ema_direction(latest: pd.Series) -> Optional[Direction]:
        if latest["ema_9"] > latest["ema_21"]:
            return Direction.LONG
        if latest["ema_9"] < latest["ema_21"]:
            return Direction.SHORT
        return None

    @staticmethod
    def _nearest_zone(price: float, zones: List[LiquidityZone], direction: Direction) -> Optional[LiquidityZone]:
        if direction == Direction.LONG:
            candidates = [zone for zone in zones if zone.price <= price]
            return max(candidates, key=lambda item: item.price, default=None)
        candidates = [zone for zone in zones if zone.price >= price]
        return min(candidates, key=lambda item: item.price, default=None)
