from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.backtests import BacktestRepository
from app.schemas import BacktestCreate, BacktestJobRead, BacktestRerun
from app.services.backtest_queue import BacktestQueue, create_queue
from app.services.backtest_service import (
    BacktestConflictError,
    BacktestNotFoundError,
    BacktestQueueError,
    BacktestService,
    BacktestValidationError,
)


router = APIRouter(prefix="/backtests", tags=["backtests"])


async def get_queue() -> AsyncIterator[BacktestQueue]:
    queue = create_queue()
    try:
        yield queue
    finally:
        await queue.redis.aclose()


def _service(session: AsyncSession, queue: BacktestQueue) -> BacktestService:
    return BacktestService(BacktestRepository(session), queue)


@router.post("", response_model=BacktestJobRead, status_code=status.HTTP_202_ACCEPTED)
async def create_backtest(
    payload: BacktestCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    queue: Annotated[BacktestQueue, Depends(get_queue)],
):
    try:
        return await _service(session, queue).create(payload)
    except BacktestNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except BacktestConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except BacktestValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except BacktestQueueError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/{job_id}", response_model=BacktestJobRead)
async def get_backtest(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    job = await BacktestRepository(session).get_job(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "backtest job not found")
    return job


@router.post(
    "/{job_id}/rerun",
    response_model=BacktestJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def rerun_backtest(
    job_id: UUID,
    payload: BacktestRerun,
    session: Annotated[AsyncSession, Depends(get_session)],
    queue: Annotated[BacktestQueue, Depends(get_queue)],
):
    try:
        return await _service(session, queue).rerun(job_id, payload)
    except BacktestNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except BacktestConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except BacktestQueueError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
