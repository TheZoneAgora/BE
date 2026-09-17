from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint(
            "timeframe IN ('1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d')",
            name="agents_timeframe_check",
        ),
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

    signals: Mapped[list["Signal"]] = relationship(back_populates="agent")


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        CheckConstraint(
            "action IN ('BUY', 'SELL', 'HOLD', 'CLOSE')",
            name="signals_action_check",
        ),
        CheckConstraint("price IS NULL OR price > 0", name="signals_price_check"),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="signals_confidence_check",
        ),
        UniqueConstraint("agent_id", "signal_id", name="signals_agent_signal_unique"),
        Index("signals_agent_generated_at_idx", "agent_id", "generated_at"),
        Index("signals_symbol_generated_at_idx", "symbol", "generated_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    signal_id: Mapped[str] = mapped_column(String(255), nullable=False)

    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    agent: Mapped[Agent] = relationship(back_populates="signals")
