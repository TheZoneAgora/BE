from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Agent, BacktestJob, BacktestResult, BacktestSignalSet


class BacktestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_agent(self, agent_id: int) -> Agent | None:
        return await self.session.get(Agent, agent_id)

    async def create_job(self, **values: object) -> BacktestJob:
        job = BacktestJob(**values)
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_job(self, job_id: UUID) -> BacktestJob | None:
        statement = (
            select(BacktestJob)
            .where(BacktestJob.id == job_id)
            .options(
                joinedload(BacktestJob.result),
                joinedload(BacktestJob.signal_set),
                joinedload(BacktestJob.agent),
            )
        )
        return (await self.session.execute(statement)).unique().scalar_one_or_none()

    async def claim_job(self, job_id: UUID, stale_seconds: int) -> bool:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=stale_seconds)
        statement = (
            update(BacktestJob)
            .where(
                BacktestJob.id == job_id,
                or_(
                    BacktestJob.status == "PENDING",
                    (
                        (BacktestJob.status == "RUNNING")
                        & (BacktestJob.locked_at < stale_before)
                    ),
                ),
            )
            .values(
                status="RUNNING",
                error_message=None,
                locked_at=now,
                started_at=func.coalesce(BacktestJob.started_at, now),
                updated_at=now,
            )
            .returning(BacktestJob.id)
        )
        claimed = (await self.session.execute(statement)).scalar_one_or_none()
        await self.session.commit()
        return claimed is not None

    async def get_or_create_signal_set(
        self,
        *,
        agent_id: int,
        strategy_version: str,
        symbol: str,
        timeframe: str,
        ohlcv_hash: str,
        signals: list[dict],
    ) -> BacktestSignalSet:
        values = {
            "agent_id": agent_id,
            "strategy_version": strategy_version,
            "symbol": symbol,
            "timeframe": timeframe,
            "ohlcv_hash": ohlcv_hash,
            "signals": signals,
        }
        statement = (
            insert(BacktestSignalSet)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_backtest_signal_set_identity")
            .returning(BacktestSignalSet.id)
        )
        signal_set_id = (await self.session.execute(statement)).scalar_one_or_none()
        if signal_set_id is None:
            signal_set_id = (
                await self.session.execute(
                    select(BacktestSignalSet.id).where(
                        BacktestSignalSet.agent_id == agent_id,
                        BacktestSignalSet.strategy_version == strategy_version,
                        BacktestSignalSet.symbol == symbol,
                        BacktestSignalSet.timeframe == timeframe,
                        BacktestSignalSet.ohlcv_hash == ohlcv_hash,
                    )
                )
            ).scalar_one()
        await self.session.commit()
        return await self.session.get(BacktestSignalSet, signal_set_id)  # type: ignore[return-value]

    async def attach_signal_set(self, job_id: UUID, signal_set_id: UUID) -> None:
        await self.session.execute(
            update(BacktestJob)
            .where(BacktestJob.id == job_id, BacktestJob.status == "RUNNING")
            .values(signal_set_id=signal_set_id, updated_at=func.now())
        )
        await self.session.commit()

    async def complete_job(
        self, job_id: UUID, result_values: dict[str, object]
    ) -> None:
        self.session.add(BacktestResult(job_id=job_id, **result_values))
        await self.session.execute(
            update(BacktestJob)
            .where(BacktestJob.id == job_id, BacktestJob.status == "RUNNING")
            .values(
                status="COMPLETED",
                completed_at=func.now(),
                updated_at=func.now(),
                locked_at=None,
            )
        )
        await self.session.commit()

    async def fail_job(self, job_id: UUID, error_message: str) -> None:
        await self.session.rollback()
        await self.session.execute(
            update(BacktestJob)
            .where(BacktestJob.id == job_id, BacktestJob.status == "RUNNING")
            .values(
                status="FAILED",
                error_message=error_message[:4000],
                completed_at=func.now(),
                updated_at=func.now(),
                locked_at=None,
            )
        )
        await self.session.commit()

    async def fail_unqueued_job(self, job_id: UUID, error_message: str) -> None:
        await self.session.rollback()
        await self.session.execute(
            update(BacktestJob)
            .where(BacktestJob.id == job_id, BacktestJob.status == "PENDING")
            .values(
                status="FAILED",
                error_message=error_message[:4000],
                completed_at=func.now(),
                updated_at=func.now(),
            )
        )
        await self.session.commit()
