from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Annotated[str, Field(min_length=1, max_length=100)]
    endpoint_url: AnyHttpUrl
    public_key: Annotated[str, Field(min_length=1, max_length=255)]

    strategy_version: Annotated[str, Field(min_length=1, max_length=50)]
    timeframe: Literal["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"]

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


class SignalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    agent_id: Annotated[int, Field(gt=0)]
    signal_id: Annotated[str, Field(min_length=1, max_length=255)]
    symbol: Annotated[str, Field(min_length=1, max_length=50)]
    action: Literal["BUY", "SELL", "HOLD", "CLOSE"]
    generated_at: datetime
    price: Annotated[Decimal | None, Field(gt=0)] = None
    confidence: Annotated[Decimal | None, Field(ge=0, le=1)] = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol", "action", mode="before")
    @classmethod
    def normalize_uppercase(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone offset")
        return value.astimezone(UTC)


class SignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    signal_id: str
    symbol: str
    timeframe: str
    action: str
    generated_at: datetime
    received_at: datetime
    price: Decimal | None
    confidence: Decimal | None
    raw_payload: dict[str, Any]
