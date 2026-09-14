from datetime import datetime
from typing import Annotated, Literal, Self

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
