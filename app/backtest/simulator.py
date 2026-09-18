from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.backtest.metrics import max_drawdown


BPS_DENOMINATOR = Decimal("10000")


@dataclass(frozen=True)
class Candle:
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class Signal:
    open_time: datetime
    action: Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Trade:
    signal_time: datetime
    execution_time: datetime
    action: Literal["BUY", "SELL"]
    price: Decimal
    quantity: Decimal
    gross_amount: Decimal
    fee: Decimal
    slippage_cost: Decimal


@dataclass(frozen=True)
class SimulationResult:
    total_return: Decimal
    max_drawdown: Decimal
    trade_count: int
    total_fees: Decimal
    total_slippage: Decimal
    final_cash: Decimal
    final_base_quantity: Decimal
    average_entry_price: Decimal
    final_equity: Decimal
    trades: list[Trade]
    equity_curve: list[Decimal]


def simulate(
    *,
    candles: list[Candle],
    signals: list[Signal],
    initial_cash: Decimal,
    order_size_quote: Decimal,
    fee_bps: Decimal,
    slippage_bps: Decimal,
) -> SimulationResult:
    if not candles:
        raise ValueError("candles must not be empty")
    if initial_cash <= 0 or order_size_quote <= 0:
        raise ValueError("initial_cash and order_size_quote must be positive")

    signal_by_time = {signal.open_time: signal for signal in signals}
    fee_rate = fee_bps / BPS_DENOMINATOR
    slippage_rate = slippage_bps / BPS_DENOMINATOR
    cash = initial_cash
    quantity = Decimal("0")
    average_entry_price = Decimal("0")
    total_fees = Decimal("0")
    total_slippage = Decimal("0")
    trades: list[Trade] = []
    equity_curve = [initial_cash]

    # A signal on candle i executes only at candle i+1 open. A final-candle signal
    # therefore never enters this loop and is intentionally ignored.
    for index, candle in enumerate(candles):
        if index:
            signal = signal_by_time.get(candles[index - 1].open_time)
            if signal is not None and signal.action == "BUY" and quantity == 0:
                fill_price = candle.open * (Decimal("1") + slippage_rate)
                # Insufficient cash policy: shrink the order so principal + fee uses
                # at most all remaining cash; never create a negative balance.
                gross_amount = min(
                    order_size_quote,
                    cash / (Decimal("1") + fee_rate),
                )
                if gross_amount > 0:
                    bought = gross_amount / fill_price
                    fee = gross_amount * fee_rate
                    slippage_cost = (fill_price - candle.open) * bought
                    cash -= gross_amount + fee
                    quantity = bought
                    average_entry_price = (gross_amount + fee) / bought
                    total_fees += fee
                    total_slippage += slippage_cost
                    trades.append(
                        Trade(
                            signal.open_time,
                            candle.open_time,
                            "BUY",
                            fill_price,
                            bought,
                            gross_amount,
                            fee,
                            slippage_cost,
                        )
                    )
            elif signal is not None and signal.action == "SELL" and quantity > 0:
                fill_price = candle.open * (Decimal("1") - slippage_rate)
                sold = quantity
                gross_amount = sold * fill_price
                fee = gross_amount * fee_rate
                slippage_cost = (candle.open - fill_price) * sold
                cash += gross_amount - fee
                quantity = Decimal("0")
                average_entry_price = Decimal("0")
                total_fees += fee
                total_slippage += slippage_cost
                trades.append(
                    Trade(
                        signal.open_time,
                        candle.open_time,
                        "SELL",
                        fill_price,
                        sold,
                        gross_amount,
                        fee,
                        slippage_cost,
                    )
                )

        equity_curve.append(cash + quantity * candle.close)

    final_equity = cash + quantity * candles[-1].close
    return SimulationResult(
        total_return=(final_equity / initial_cash) - Decimal("1"),
        max_drawdown=max_drawdown(equity_curve),
        trade_count=len(trades),
        total_fees=total_fees,
        total_slippage=total_slippage,
        final_cash=cash,
        final_base_quantity=quantity,
        average_entry_price=average_entry_price,
        final_equity=final_equity,
        trades=trades,
        equity_curve=equity_curve,
    )
