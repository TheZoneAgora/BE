from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Annotated[str, Field(min_length=1, max_length=100)]
    endpoint_url: AnyHttpUrl
    public_key: Annotated[str, Field(min_length=1, max_length=255)]

    strategy_version: Annotated[str, Field(min_length=1, max_length=50)]
    timeframe: Literal["5m", "15m", "1h"]

    max_position_bps: Annotated[int, Field(ge=1, le=5000)]
    max_order_bps: Annotated[int, Field(ge=1, le=5000)]
    max_daily_loss_bps: Annotated[int, Field(ge=1, le=3000)]

    allowed_symbols: Annotated[list[str], Field(min_length=1)]

    @field_validator("allowed_symbols")
    @classmethod
    def validate_symbols(cls, symbols: list[str]) -> list[str]:
        normalized = [symbol.strip() for symbol in symbols]
        if any(not symbol for symbol in normalized):
            raise ValueError("allowed_symbols cannot contain empty values")
        return normalized

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.max_order_bps > self.max_position_bps:
            raise ValueError("max_order_bps는 max_position_bps보다 클 수 없습니다.")

        if len(set(self.allowed_symbols)) != len(self.allowed_symbols):
            raise ValueError("allowed_symbols에 중복 종목이 있습니다.")

        return self


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    endpoint_url: str
    public_key: str

    strategy_version: str
    timeframe: str

    max_position_bps: int
    max_order_bps: int
    max_daily_loss_bps: int
    min_trade_interval_bars: int

    allow_short: bool
    max_open_positions: int

    allowed_order_types: list[str]
    allowed_symbols: list[str]

    status: str
    created_at: datetime
    updated_at: datetime


class OhlcvCandle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open_time: datetime
    open: Annotated[Decimal, Field(gt=0)]
    high: Annotated[Decimal, Field(gt=0)]
    low: Annotated[Decimal, Field(gt=0)]
    close: Annotated[Decimal, Field(gt=0)]
    volume: Annotated[Decimal, Field(ge=0)]

    @field_validator("open_time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("open_time must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_prices(self) -> Self:
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be the candle's highest price")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be the candle's lowest price")
        return self


class BacktestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: int
    symbol: Annotated[str, Field(min_length=1, max_length=40)]
    timeframe: Annotated[str, Field(min_length=1, max_length=20)]
    candles: Annotated[list[OhlcvCandle], Field(min_length=1)]
    initial_cash: Annotated[Decimal, Field(gt=0)]
    order_size_quote: Annotated[Decimal, Field(gt=0)]
    fee_bps: Annotated[Decimal, Field(ge=0, le=10000)] = Decimal("0")
    slippage_bps: Annotated[Decimal, Field(ge=0, le=10000)] = Decimal("0")

    @field_validator("candles")
    @classmethod
    def validate_candle_order(cls, candles: list[OhlcvCandle]) -> list[OhlcvCandle]:
        times = [candle.open_time for candle in candles]
        if any(current >= following for current, following in zip(times, times[1:])):
            raise ValueError("candles must be strictly ordered by open_time")
        return candles


class BacktestRerun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fee_bps: Annotated[Decimal | None, Field(ge=0, le=10000)] = None
    slippage_bps: Annotated[Decimal | None, Field(ge=0, le=10000)] = None


class BacktestResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_return: Decimal
    max_drawdown: Decimal
    trade_count: int
    total_fees: Decimal
    total_slippage: Decimal
    total_costs: Decimal
    final_cash: Decimal
    final_base_quantity: Decimal
    average_entry_price: Decimal
    final_equity: Decimal
    trades: list[dict]


class BacktestJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: int
    parent_job_id: UUID | None
    signal_set_id: UUID | None
    symbol: str
    timeframe: str
    ohlcv_hash: str
    initial_cash: Decimal
    order_size_quote: Decimal
    fee_bps: Decimal
    slippage_bps: Decimal
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    result: BacktestResultRead | None = None


class AgentSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open_time: datetime
    action: Literal["BUY", "SELL"]

    @field_validator("open_time")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("signal open_time must include a timezone")
        return value.astimezone(timezone.utc)


class AgentBacktestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signals: list[AgentSignal]
