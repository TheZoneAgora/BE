from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from app.schemas import AgentBacktestResponse, OhlcvCandle


class AgentBacktestError(RuntimeError):
    pass


class AgentBacktestClient:
    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds

    async def get_signals(
        self,
        *,
        endpoint_url: str,
        symbol: str,
        timeframe: str,
        candles: list[OhlcvCandle],
    ) -> AgentBacktestResponse:
        url = f"{endpoint_url.rstrip('/')}/backtest"
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "ohlcv": [candle.model_dump(mode="json") for candle in candles],
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AgentBacktestError(f"agent HTTP request failed: {exc}") from exc

        try:
            parsed = AgentBacktestResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise AgentBacktestError(f"invalid agent response: {exc}") from exc

        validate_agent_response(parsed, candles)
        return parsed


def validate_agent_response(
    parsed: AgentBacktestResponse, candles: list[OhlcvCandle]
) -> None:
    candle_times = {_utc(candle.open_time) for candle in candles}
    signal_times: set[datetime] = set()
    for signal in parsed.signals:
        signal_time = _utc(signal.open_time)
        if signal_time not in candle_times:
            raise AgentBacktestError(
                f"signal time is not present in input candles: {signal.open_time.isoformat()}"
            )
        if signal_time in signal_times:
            raise AgentBacktestError(
                f"duplicate signal time: {signal.open_time.isoformat()}"
            )
        signal_times.add(signal_time)


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)
