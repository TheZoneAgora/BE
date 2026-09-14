ALTER TABLE agents
    ADD COLUMN IF NOT EXISTS min_trade_interval_bars INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS allow_short BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS max_open_positions INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS allowed_order_types TEXT[] NOT NULL DEFAULT ARRAY['MARKET']::TEXT[];

ALTER TABLE agents
    ADD CONSTRAINT agents_min_trade_interval_check
        CHECK (min_trade_interval_bars >= 1),
    ADD CONSTRAINT agents_allow_short_check
        CHECK (allow_short = FALSE),
    ADD CONSTRAINT agents_max_open_positions_check
        CHECK (max_open_positions = 1),
    ADD CONSTRAINT agents_order_types_check
        CHECK (allowed_order_types = ARRAY['MARKET']::TEXT[]);
