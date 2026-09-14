from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint("timeframe IN ('5m', '15m', '1h')"),
        CheckConstraint("max_position_bps BETWEEN 1 AND 5000"),
        CheckConstraint(
            "max_order_bps BETWEEN 1 AND 5000 "
            "AND max_order_bps <= max_position_bps"
        ),
        CheckConstraint("max_daily_loss_bps BETWEEN 1 AND 3000"),
        CheckConstraint("CARDINALITY(allowed_symbols) >= 1"),
        CheckConstraint("status IN ('ACTIVE', 'PAUSED', 'ARCHIVED')"),
        CheckConstraint("min_trade_interval_bars >= 1"),
        CheckConstraint("allow_short = FALSE"),
        CheckConstraint("max_open_positions = 1"),
        CheckConstraint("allowed_order_types = ARRAY['MARKET']::TEXT[]"),
        UniqueConstraint("name", "strategy_version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    endpoint_url: Mapped[str] = mapped_column(String(2048))
    public_key: Mapped[str] = mapped_column(String(255))

    strategy_version: Mapped[str] = mapped_column(String(50))
    timeframe: Mapped[str] = mapped_column(String(10))

    max_position_bps: Mapped[int]
    max_order_bps: Mapped[int]
    max_daily_loss_bps: Mapped[int]
    min_trade_interval_bars: Mapped[int] = mapped_column(default=1, server_default="1")

    allow_short: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("FALSE")
    )
    max_open_positions: Mapped[int] = mapped_column(default=1, server_default="1")

    allowed_order_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        default=lambda: ["MARKET"],
        server_default=text("ARRAY['MARKET']::TEXT[]"),
    )
    allowed_symbols: Mapped[list[str]] = mapped_column(ARRAY(Text))

    status: Mapped[str] = mapped_column(
        String(20), default="ACTIVE", server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
