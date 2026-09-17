import asyncio
import logging
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.config import get_settings
from app.database import close_database, session_factory
from app.repositories.backtests import BacktestRepository
from app.services.agent_backtest_client import AgentBacktestClient
from app.services.backtest_service import BacktestProcessor


logger = logging.getLogger(__name__)


class BacktestWorker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.redis = Redis.from_url(self.settings.redis_url, decode_responses=True)

    async def run(self) -> None:
        await self._ensure_group()
        while True:
            recovered = await self.redis.xautoclaim(
                self.settings.backtest_stream,
                self.settings.backtest_consumer_group,
                self.settings.backtest_consumer_name,
                min_idle_time=self.settings.backtest_worker_stale_seconds * 1000,
                start_id="0-0",
                count=1,
            )
            messages = recovered[1]
            if not messages:
                response = await self.redis.xreadgroup(
                    self.settings.backtest_consumer_group,
                    self.settings.backtest_consumer_name,
                    {self.settings.backtest_stream: ">"},
                    count=1,
                    block=5000,
                )
                messages = response[0][1] if response else []
            for message_id, fields in messages:
                await self._handle(message_id, fields)

    async def _ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(
                self.settings.backtest_stream,
                self.settings.backtest_consumer_group,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def _handle(self, message_id: str, fields: dict[str, str]) -> None:
        try:
            if set(fields) != {"job_id"}:
                raise ValueError("stream message must contain only job_id")
            job_id = UUID(fields["job_id"])
            async with session_factory() as session:
                processor = BacktestProcessor(
                    BacktestRepository(session),
                    AgentBacktestClient(
                        self.settings.agent_backtest_timeout_seconds
                    ),
                    self.settings.backtest_worker_stale_seconds,
                )
                await processor.process(job_id)
            # ACK only after COMPLETED/FAILED persistence or an idempotent no-op.
            await self.redis.xack(
                self.settings.backtest_stream,
                self.settings.backtest_consumer_group,
                message_id,
            )
        except Exception:
            logger.exception("backtest message processing failed", extra={"id": message_id})
            await asyncio.sleep(1)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    worker = BacktestWorker()
    try:
        await worker.run()
    finally:
        await worker.redis.aclose()
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
