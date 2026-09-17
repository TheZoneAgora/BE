from uuid import UUID

from redis.asyncio import Redis

from app.config import get_settings


class BacktestQueue:
    def __init__(self, redis: Redis, stream: str):
        self.redis = redis
        self.stream = stream

    async def enqueue(self, job_id: UUID) -> str:
        # Deliberately keep the durable message contract to job_id only.
        return await self.redis.xadd(self.stream, {"job_id": str(job_id)})


def create_queue() -> BacktestQueue:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return BacktestQueue(redis, settings.backtest_stream)
