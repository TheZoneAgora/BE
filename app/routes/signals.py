from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Agent, Signal
from app.schemas import SignalCreate, SignalRead


router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("", response_model=SignalRead, status_code=status.HTTP_201_CREATED)
async def create_signal(
    payload: SignalCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Signal:
    agent = await session.get(Agent, payload.agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    if agent.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Signals can only be stored for an ACTIVE agent",
        )
    if payload.symbol not in {symbol.upper() for symbol in agent.allowed_symbols}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The symbol is not allowed for this agent",
        )

    signal = Signal(
        **payload.model_dump(),
        timeframe=agent.timeframe,
    )
    session.add(signal)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A signal with this signal_id already exists for the agent",
        ) from exc

    await session.refresh(signal)
    return signal


@router.get("", response_model=list[SignalRead])
async def list_signals(
    session: Annotated[AsyncSession, Depends(get_session)],
    agent_id: Annotated[int | None, Query(gt=0)] = None,
    symbol: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    order: Literal["asc", "desc"] = "asc",
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[Signal]:
    if start_at is not None and start_at.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_at must include a timezone offset",
        )
    if end_at is not None and end_at.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_at must include a timezone offset",
        )
    if start_at is not None and end_at is not None and start_at > end_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_at must be earlier than or equal to end_at",
        )

    statement: Select[tuple[Signal]] = select(Signal)
    if agent_id is not None:
        statement = statement.where(Signal.agent_id == agent_id)
    if symbol is not None:
        statement = statement.where(Signal.symbol == symbol.upper())
    if start_at is not None:
        statement = statement.where(Signal.generated_at >= start_at)
    if end_at is not None:
        statement = statement.where(Signal.generated_at <= end_at)

    ordering = Signal.generated_at.asc() if order == "asc" else Signal.generated_at.desc()
    result = await session.scalars(statement.order_by(ordering, Signal.id).limit(limit))
    return list(result)
