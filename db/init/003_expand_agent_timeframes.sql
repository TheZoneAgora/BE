ALTER TABLE agents
    DROP CONSTRAINT IF EXISTS agents_timeframe_check;

ALTER TABLE agents
    ADD CONSTRAINT agents_timeframe_check
        CHECK (timeframe IN ('1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d'));
