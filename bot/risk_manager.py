from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from bot.config import RiskConfig
from bot.models import ActiveTrade, PositionPlan, SetupType, TradeSignal


@dataclass(slots=True)
class AccountSnapshot:
    total_usdt: float
    free_usdt: float


class RiskManager:
    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    def parse_balance(self, balance: Dict) -> AccountSnapshot:
        usdt_total = float(balance.get("USDT", {}).get("total", 0.0))
        usdt_free = float(balance.get("USDT", {}).get("free", 0.0))
        if usdt_total <= 0:
            totals = balance.get("total", {})
            free = balance.get("free", {})
            usdt_total = float(totals.get("USDT", 0.0))
            usdt_free = float(free.get("USDT", 0.0))
        return AccountSnapshot(total_usdt=usdt_total, free_usdt=usdt_free)

    def can_open_trade(
        self,
        signal: TradeSignal,
        account: AccountSnapshot,
        active_trades: Iterable[ActiveTrade],
    ) -> tuple[bool, str]:
        trades = list(active_trades)
        if len(trades) >= self.config.max_active_trades:
            return False, "Max active trades reached"
        if any(trade.symbol == signal.symbol for trade in trades):
            return False, "Trade already active for symbol"
        if len(trades) == 1 and signal.score < 8:
            return False, "Second trade requires score >= 8"

        reserved_buffer = account.total_usdt * self.config.capital_buffer
        allocatable = max(account.free_usdt - reserved_buffer, 0.0)
        required_margin = account.total_usdt * self.config.capital_usage_per_trade
        if allocatable < required_margin:
            return False, "Insufficient free capital after buffer"
        return True, "OK"

    def build_position_plan(
        self,
        signal: TradeSignal,
        account: AccountSnapshot,
        leverage: int,
        market_info: Optional[Dict] = None,
    ) -> PositionPlan:
        allocated_margin = account.total_usdt * self.config.capital_usage_per_trade
        risk_amount = account.total_usdt * self.config.risk_per_trade
        stop_distance = abs(signal.entry - signal.stop_loss)
        if stop_distance <= 0:
            raise ValueError("Invalid stop distance")

        quantity_by_risk = risk_amount / stop_distance
        max_notional = allocated_margin * leverage
        quantity_by_capital = max_notional / signal.entry
        quantity = min(quantity_by_risk, quantity_by_capital)
        quantity = self._normalize_quantity(quantity, market_info)

        notional_value = quantity * signal.entry
        margin_required = notional_value / leverage
        return PositionPlan(
            symbol=signal.symbol,
            direction=signal.direction,
            entry=signal.entry,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            quantity=quantity,
            leverage=leverage,
            notional_value=notional_value,
            margin_required=margin_required,
            risk_amount=risk_amount,
            rr_ratio=signal.rr_ratio,
            score=signal.score,
            setup=signal.setup,
            entry_order_type=self._resolve_entry_order_type(signal.setup),
        )

    @staticmethod
    def _normalize_quantity(quantity: float, market_info: Optional[Dict]) -> float:
        if quantity <= 0:
            raise ValueError("Calculated quantity must be positive")
        if not market_info:
            return round(quantity, 6)
        precision = market_info.get("precision", {}).get("amount")
        minimum = market_info.get("limits", {}).get("amount", {}).get("min")
        if precision is not None:
            quantity = round(quantity, int(precision))
        if minimum is not None and quantity < minimum:
            raise ValueError(f"Quantity {quantity} is below minimum amount {minimum}")
        return quantity

    @staticmethod
    def _resolve_entry_order_type(setup: SetupType) -> str:
        if setup == SetupType.LIQUIDITY_SWEEP_REVERSAL:
            return "market"
        return "limit"
