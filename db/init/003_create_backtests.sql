CREATE TABLE backtest_signal_sets (
    id UUID PRIMARY KEY,
    agent_id BIGINT NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
    strategy_version VARCHAR(50) NOT NULL,
    symbol VARCHAR(40) NOT NULL,
    timeframe VARCHAR(20) NOT NULL,
    ohlcv_hash VARCHAR(64) NOT NULL,
    signals JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_backtest_signal_set_identity UNIQUE (
        agent_id, strategy_version, symbol, timeframe, ohlcv_hash
    )
);

CREATE INDEX ix_backtest_signal_sets_lookup
    ON backtest_signal_sets (agent_id, ohlcv_hash);

CREATE TABLE backtest_jobs (
    id UUID PRIMARY KEY,
    agent_id BIGINT NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
    parent_job_id UUID REFERENCES backtest_jobs(id) ON DELETE SET NULL,
    signal_set_id UUID REFERENCES backtest_signal_sets(id) ON DELETE RESTRICT,
    symbol VARCHAR(40) NOT NULL,
    timeframe VARCHAR(20) NOT NULL,
    ohlcv_hash VARCHAR(64) NOT NULL,
    candles JSONB NOT NULL,
    initial_cash NUMERIC(36, 18) NOT NULL,
    order_size_quote NUMERIC(36, 18) NOT NULL,
    fee_bps NUMERIC(12, 4) NOT NULL,
    slippage_bps NUMERIC(12, 4) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    locked_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT backtest_jobs_status_check
        CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')),
    CONSTRAINT backtest_jobs_initial_cash_check CHECK (initial_cash > 0),
    CONSTRAINT backtest_jobs_order_size_check CHECK (order_size_quote > 0),
    CONSTRAINT backtest_jobs_fee_check CHECK (fee_bps BETWEEN 0 AND 10000),
    CONSTRAINT backtest_jobs_slippage_check CHECK (slippage_bps BETWEEN 0 AND 10000)
);

CREATE INDEX ix_backtest_jobs_status_created_at
    ON backtest_jobs (status, created_at);
CREATE INDEX ix_backtest_jobs_agent_hash
    ON backtest_jobs (agent_id, ohlcv_hash);

CREATE TABLE backtest_results (
    job_id UUID PRIMARY KEY REFERENCES backtest_jobs(id) ON DELETE CASCADE,
    total_return NUMERIC(36, 18) NOT NULL,
    max_drawdown NUMERIC(36, 18) NOT NULL,
    trade_count INTEGER NOT NULL CHECK (trade_count >= 0),
    total_fees NUMERIC(36, 18) NOT NULL CHECK (total_fees >= 0),
    total_slippage NUMERIC(36, 18) NOT NULL CHECK (total_slippage >= 0),
    total_costs NUMERIC(36, 18) NOT NULL CHECK (total_costs >= 0),
    final_cash NUMERIC(36, 18) NOT NULL,
    final_base_quantity NUMERIC(36, 18) NOT NULL,
    average_entry_price NUMERIC(36, 18) NOT NULL,
    final_equity NUMERIC(36, 18) NOT NULL,
    trades JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
