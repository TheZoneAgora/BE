CREATE TABLE agents (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    endpoint_url VARCHAR(2048) NOT NULL,
    public_key VARCHAR(255) NOT NULL,

    strategy_version VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,

    max_position_bps INTEGER NOT NULL,
    max_order_bps INTEGER NOT NULL,
    max_daily_loss_bps INTEGER NOT NULL,

    allowed_symbols TEXT[] NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT agents_timeframe_check
        CHECK (timeframe IN ('5m', '15m', '1h')),

    CONSTRAINT agents_max_position_check
        CHECK (max_position_bps BETWEEN 1 AND 5000),

    CONSTRAINT agents_max_order_check
        CHECK (
            max_order_bps BETWEEN 1 AND 5000
            AND max_order_bps <= max_position_bps
        ),

    CONSTRAINT agents_daily_loss_check
        CHECK (max_daily_loss_bps BETWEEN 1 AND 3000),

    CONSTRAINT agents_symbols_check
        CHECK (CARDINALITY(allowed_symbols) >= 1),

    CONSTRAINT agents_status_check
        CHECK (status IN ('ACTIVE', 'PAUSED', 'ARCHIVED')),

    CONSTRAINT agents_name_version_unique
        UNIQUE (name, strategy_version)
);
