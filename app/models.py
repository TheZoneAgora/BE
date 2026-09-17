from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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


class BacktestJob(Base):
    __tablename__ = "backtest_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')"),
        CheckConstraint("initial_cash > 0"),
        CheckConstraint("order_size_quote > 0"),
        CheckConstraint("fee_bps >= 0 AND fee_bps <= 10000"),
        CheckConstraint("slippage_bps >= 0 AND slippage_bps <= 10000"),
        Index("ix_backtest_jobs_status_created_at", "status", "created_at"),
        Index("ix_backtest_jobs_agent_hash", "agent_id", "ohlcv_hash"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    agent_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    parent_job_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("backtest_jobs.id", ondelete="SET NULL")
    )
    signal_set_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("backtest_signal_sets.id", ondelete="RESTRICT"),
    )
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(20), nullable=False)
    ohlcv_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    candles: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    order_size_quote: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    fee_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    slippage_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", server_default="PENDING"
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    agent: Mapped[Agent] = relationship()
    signal_set: Mapped["BacktestSignalSet | None"] = relationship(
        foreign_keys=[signal_set_id]
    )
    result: Mapped["BacktestResult | None"] = relationship(
        back_populates="job", uselist=False
    )


class BacktestSignalSet(Base):
    __tablename__ = "backtest_signal_sets"
    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "strategy_version",
            "symbol",
            "timeframe",
            "ohlcv_hash",
            name="uq_backtest_signal_set_identity",
        ),
        Index("ix_backtest_signal_sets_lookup", "agent_id", "ohlcv_hash"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    agent_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    strategy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(20), nullable=False)
    ohlcv_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signals: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BacktestResult(Base):
    __tablename__ = "backtest_results"
    __table_args__ = (
        CheckConstraint("trade_count >= 0"),
        CheckConstraint("total_fees >= 0"),
        CheckConstraint("total_slippage >= 0"),
        CheckConstraint("total_costs >= 0"),
    )

    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("backtest_jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    total_return: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    trade_count: Mapped[int] = mapped_column(nullable=False)
    total_fees: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    total_slippage: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    total_costs: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    final_cash: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    final_base_quantity: Mapped[Decimal] = mapped_column(
        Numeric(36, 18), nullable=False
    )
    average_entry_price: Mapped[Decimal] = mapped_column(
        Numeric(36, 18), nullable=False
    )
    final_equity: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    trades: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    job: Mapped[BacktestJob] = relationship(back_populates="result")
