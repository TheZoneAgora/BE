import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from redis.exceptions import RedisError

from app.backtest.simulator import Candle, Signal, simulate
from app.models import BacktestJob
from app.repositories.backtests import BacktestRepository
from app.schemas import BacktestCreate, BacktestRerun, OhlcvCandle
from app.services.agent_backtest_client import AgentBacktestClient
from app.services.backtest_queue import BacktestQueue


class BacktestNotFoundError(RuntimeError):
    pass


class BacktestConflictError(RuntimeError):
    pass


class BacktestValidationError(RuntimeError):
    pass


class BacktestQueueError(RuntimeError):
    pass


class BacktestService:
    def __init__(self, repository: BacktestRepository, queue: BacktestQueue):
        self.repository = repository
        self.queue = queue

    async def create(self, payload: BacktestCreate) -> BacktestJob:
        agent = await self.repository.get_agent(payload.agent_id)
        if agent is None:
            raise BacktestNotFoundError("agent not found")
        if agent.status != "ACTIVE":
            raise BacktestConflictError("agent is not active")
        if payload.symbol not in agent.allowed_symbols:
            raise BacktestValidationError("symbol is not allowed by the agent")
        if payload.timeframe != agent.timeframe:
            raise BacktestValidationError("timeframe does not match the agent")

        candles = _candles_for_storage(payload.candles)
        job = await self.repository.create_job(
            agent_id=payload.agent_id,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            candles=candles,
            ohlcv_hash=ohlcv_hash(candles),
            initial_cash=payload.initial_cash,
            order_size_quote=payload.order_size_quote,
            fee_bps=payload.fee_bps,
            slippage_bps=payload.slippage_bps,
            status="PENDING",
        )
        await self._enqueue(job)
        return await self.get(job.id)

    async def get(self, job_id: UUID) -> BacktestJob:
        job = await self.repository.get_job(job_id)
        if job is None:
            raise BacktestNotFoundError("backtest job not found")
        return job

    async def rerun(self, job_id: UUID, payload: BacktestRerun) -> BacktestJob:
        source = await self.get(job_id)
        if source.signal_set is None:
            raise BacktestConflictError("the source job has no reusable signal set")
        if source.signal_set.ohlcv_hash != source.ohlcv_hash:
            raise BacktestConflictError("source signal set does not match the OHLCV")
        job = await self.repository.create_job(
            agent_id=source.agent_id,
            parent_job_id=source.id,
            signal_set_id=source.signal_set_id,
            symbol=source.symbol,
            timeframe=source.timeframe,
            candles=source.candles,
            ohlcv_hash=source.ohlcv_hash,
            initial_cash=source.initial_cash,
            order_size_quote=source.order_size_quote,
            fee_bps=source.fee_bps if payload.fee_bps is None else payload.fee_bps,
            slippage_bps=(
                source.slippage_bps
                if payload.slippage_bps is None
                else payload.slippage_bps
            ),
            status="PENDING",
        )
        await self._enqueue(job)
        return await self.get(job.id)

    async def _enqueue(self, job: BacktestJob) -> None:
        try:
            await self.queue.enqueue(job.id)
        except RedisError as exc:
            await self.repository.fail_unqueued_job(
                job.id, f"Redis enqueue failed: {exc}"
            )
            raise BacktestQueueError("backtest queue is unavailable") from exc


class BacktestProcessor:
    def __init__(
        self,
        repository: BacktestRepository,
        agent_client: AgentBacktestClient,
        stale_seconds: int,
    ):
        self.repository = repository
        self.agent_client = agent_client
        self.stale_seconds = stale_seconds

    async def process(self, job_id: UUID) -> None:
        claimed = await self.repository.claim_job(job_id, self.stale_seconds)
        if not claimed:
            # Terminal jobs and jobs actively owned by another worker are idempotent no-ops.
            return

        try:
            job = await self.repository.get_job(job_id)
            if job is None:
                raise BacktestNotFoundError("backtest job disappeared after claim")
            candles = [OhlcvCandle.model_validate(item) for item in job.candles]
            signal_set = job.signal_set
            if signal_set is not None:
                if (
                    signal_set.agent_id != job.agent_id
                    or signal_set.strategy_version != job.agent.strategy_version
                    or signal_set.symbol != job.symbol
                    or signal_set.timeframe != job.timeframe
                    or signal_set.ohlcv_hash != job.ohlcv_hash
                ):
                    raise BacktestConflictError(
                        "stored signal set does not match this job"
                    )
                stored_signals = signal_set.signals
            else:
                response = await self.agent_client.get_signals(
                    endpoint_url=job.agent.endpoint_url,
                    symbol=job.symbol,
                    timeframe=job.timeframe,
                    candles=candles,
                )
                stored_signals = [
                    signal.model_dump(mode="json") for signal in response.signals
                ]
                signal_set = await self.repository.get_or_create_signal_set(
                    agent_id=job.agent_id,
                    strategy_version=job.agent.strategy_version,
                    symbol=job.symbol,
                    timeframe=job.timeframe,
                    ohlcv_hash=job.ohlcv_hash,
                    signals=stored_signals,
                )
                await self.repository.attach_signal_set(job.id, signal_set.id)

            result = simulate(
                candles=[_domain_candle(candle) for candle in candles],
                signals=[
                    Signal(
                        open_time=_parse_datetime(item["open_time"]),
                        action=item["action"],
                    )
                    for item in stored_signals
                ],
                initial_cash=job.initial_cash,
                order_size_quote=job.order_size_quote,
                fee_bps=job.fee_bps,
                slippage_bps=job.slippage_bps,
            )
            trades = []
            for trade in result.trades:
                item = asdict(trade)
                item["signal_time"] = trade.signal_time.isoformat()
                item["execution_time"] = trade.execution_time.isoformat()
                for key in (
                    "price",
                    "quantity",
                    "gross_amount",
                    "fee",
                    "slippage_cost",
                ):
                    item[key] = str(item[key])
                trades.append(item)
            await self.repository.complete_job(
                job.id,
                {
                    "total_return": result.total_return,
                    "max_drawdown": result.max_drawdown,
                    "trade_count": result.trade_count,
                    "total_fees": result.total_fees,
                    "total_slippage": result.total_slippage,
                    "total_costs": result.total_fees + result.total_slippage,
                    "final_cash": result.final_cash,
                    "final_base_quantity": result.final_base_quantity,
                    "average_entry_price": result.average_entry_price,
                    "final_equity": result.final_equity,
                    "trades": trades,
                },
            )
        except Exception as exc:
            await self.repository.fail_job(job_id, f"{type(exc).__name__}: {exc}")


def ohlcv_hash(candles: list[dict]) -> str:
    canonical = json.dumps(
        candles, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _candles_for_storage(candles: list[OhlcvCandle]) -> list[dict]:
    return [candle.model_dump(mode="json") for candle in candles]


def _domain_candle(candle: OhlcvCandle) -> Candle:
    return Candle(
        open_time=candle.open_time,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
    )


def _parse_datetime(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return parsed.astimezone(timezone.utc)
