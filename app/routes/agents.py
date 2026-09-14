from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Agent
from app.schemas import AgentManifest, AgentRead


router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentManifest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Agent:
    agent = Agent(
        **payload.model_dump(exclude={"endpoint_url"}),
        endpoint_url=str(payload.endpoint_url),
        min_trade_interval_bars=1,
        allow_short=False,
        max_open_positions=1,
        allowed_order_types=["MARKET"],
    )
    session.add(agent)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An agent with this name and strategy_version already exists",
        ) from exc

    await session.refresh(agent)
    return agent
