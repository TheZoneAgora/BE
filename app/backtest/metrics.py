from decimal import Decimal


def max_drawdown(equity_curve: list[Decimal]) -> Decimal:
    """Return positive peak-to-trough drawdown as a ratio."""
    if not equity_curve:
        return Decimal("0")
    peak = equity_curve[0]
    result = Decimal("0")
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak:
            result = max(result, (peak - equity) / peak)
    return result
