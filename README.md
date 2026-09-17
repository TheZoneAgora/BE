# Agora Backend

에이전트 등록을 위한 FastAPI 백엔드입니다. FastAPI, PostgreSQL, Redis를 하나의 Docker Compose 구성으로 실행합니다.

## 배포 주소

현재 Oracle Cloud의 `agora-hackathon` 인스턴스에서 실행 중입니다.

- API base URL: `http://150.230.200.147:8000`
- Swagger UI: [http://150.230.200.147:8000/docs](http://150.230.200.147:8000/docs)
- OpenAPI schema: [http://150.230.200.147:8000/openapi.json](http://150.230.200.147:8000/openapi.json)
- Health check: [http://150.230.200.147:8000/health](http://150.230.200.147:8000/health)
- Agent registration: `POST http://150.230.200.147:8000/agents`
- Signal ingestion: `POST http://150.230.200.147:8000/signals`
- Signal history: `GET http://150.230.200.147:8000/signals`

현재 해커톤 배포는 HTTP와 포트 `8000`을 사용합니다. PostgreSQL `5432`와 Redis `6379`는 외부에 공개하지 않습니다.

## API

### 상태 확인

```bash
curl http://150.230.200.147:8000/health
```

정상 응답:

```json
{
  "status": "ok",
  "database": "ok"
}
```

### 에이전트 등록

`POST /agents`

```bash
curl -X POST http://150.230.200.147:8000/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Momentum Agent",
    "endpoint_url": "https://agent.example.com/decide",
    "public_key": "0x1234567890abcdef",
    "strategy_version": "1.0.0",
    "timeframe": "5m",
    "max_position_bps": 5000,
    "max_order_bps": 2500,
    "max_daily_loss_bps": 1000,
    "allowed_symbols": ["SUI_USDC"]
  }'
```

서버는 다음 정책을 고정해서 저장합니다. 클라이언트 요청에는 이 값을 넣지 않습니다.

```json
{
  "min_trade_interval_bars": 1,
  "allow_short": false,
  "max_open_positions": 1,
  "allowed_order_types": ["MARKET"]
}
```

주요 검증 규칙:

- `timeframe`: `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d` 중 하나
  - `m`: 분봉 (`1m`, `3m`, `5m`, `15m`, `30m`)
  - `h`: 시간봉 (`1h` = 60분봉, `4h` = 4시간봉)
  - `1d`: 일봉 (Daily)
- `max_position_bps`: 1~5000
- `max_order_bps`: 1~5000이며 `max_position_bps` 이하
- `max_daily_loss_bps`: 1~3000
- `allowed_symbols`: 하나 이상이며 중복과 빈 문자열 불가
- 동일한 `name`과 `strategy_version` 조합은 중복 등록 불가

응답 상태:

- `201 Created`: 등록 성공
- `409 Conflict`: 같은 이름과 전략 버전이 이미 존재
- `422 Unprocessable Entity`: 요청 형식 또는 값 검증 실패

### 매매 시그널 저장

`POST /signals`

등록된 ACTIVE 에이전트가 생성한 시그널을 저장합니다. `signal_id`는 에이전트가
발급하는 고유 ID이며, 같은 에이전트에서 재사용할 수 없습니다. `generated_at`에는
반드시 타임존을 포함해야 합니다. 서버는 에이전트 등록 당시의 `timeframe`과 실제
수신 시각인 `received_at`을 함께 저장합니다.

```bash
curl -X POST http://150.230.200.147:8000/signals \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": 1,
    "signal_id": "momentum-20260917-0001",
    "symbol": "SUI_USDC",
    "action": "BUY",
    "generated_at": "2026-09-17T09:30:00+09:00",
    "price": "3.450000000000000000",
    "confidence": "0.875",
    "raw_payload": {
      "reason": "fast_ma_crossed_above_slow_ma"
    }
  }'
```

주요 검증 규칙:

- `agent_id`: 등록되어 있고 상태가 `ACTIVE`인 에이전트
- `signal_id`: 에이전트별 고유 값
- `symbol`: 해당 에이전트의 `allowed_symbols`에 등록된 종목
- `action`: `BUY`, `SELL`, `HOLD`, `CLOSE` 중 하나
- `generated_at`: 타임존 오프셋이 포함된 시그널 발생 시각
- `price`: 선택 값이며 입력 시 0보다 큰 값
- `confidence`: 선택 값이며 0~1 사이 값
- `raw_payload`: 향후 전략별 필드를 보존하기 위한 JSON 객체

응답 상태:

- `201 Created`: 저장 성공
- `404 Not Found`: 에이전트가 존재하지 않음
- `409 Conflict`: 비활성 에이전트 또는 중복 `signal_id`
- `422 Unprocessable Entity`: 요청 형식, 종목 또는 값 검증 실패

### 매매 시그널 조회

`GET /signals`는 백테스트 및 라이브 테스트가 저장된 시그널을 시간순으로 조회할 때
사용합니다. `agent_id`, `symbol`, `start_at`, `end_at`, `order`, `limit`으로 필터링할
수 있으며 기본 정렬은 시그널 발생 시각 오름차순입니다.

```bash
curl "http://150.230.200.147:8000/signals?agent_id=1&symbol=SUI_USDC&order=asc&limit=500"
```

## 로컬 실행

이 프로젝트는 개발용과 서버용 Compose 파일을 따로 두지 않습니다. 같은 `compose.yaml`을 사용하고 환경별 값만 `.env`에서 관리합니다.

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
```

로컬 주소:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- OpenAPI schema: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
- Agent registration: `POST http://localhost:8000/agents`
- Signal ingestion: `POST http://localhost:8000/signals`
- Signal history: `GET http://localhost:8000/signals`

기본 `.env` 형식:

```dotenv
POSTGRES_DB=agora
POSTGRES_USER=agora
POSTGRES_PASSWORD=replace_with_a_long_random_password
API_PORT=8000
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

CORS에는 브라우저의 origin만 입력합니다. 예를 들어 `http://localhost:3000/agora`에서 요청하더라도 설정값은 경로를 제외한 `http://localhost:3000`입니다. 현재 CORS는 `GET`, `POST` 요청과 `Content-Type` 헤더를 허용합니다.

기존 PostgreSQL 볼륨에 시그널 테이블을 추가하려면 배포 전에 마이그레이션 SQL을
한 번 실행합니다. 새 볼륨에서는 Docker 초기화 과정에서 자동 실행됩니다.

```bash
sudo docker compose exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  < db/init/004_create_signals.sql
```

## Oracle Cloud 구성

- Compute instance: `agora-hackathon`
- Public IP: `150.230.200.147`
- 공개 포트: TCP `22`, TCP `8000`
- 내부 전용 포트: PostgreSQL `5432`, Redis `6379`
- 컨테이너 재시작 정책: `unless-stopped`
- PostgreSQL 데이터: Docker volume `postgres_data`
- Redis 데이터: Docker volume `redis_data`
- 메모리 보완: 2GB swap

실행 컨테이너:

- `agora-api`
- `agora-postgres`
- `agora-redis`

## 서버 업데이트

Oracle 서버에 SSH로 접속한 뒤 실행합니다.

```bash
cd ~/BE
git pull --ff-only
sudo docker compose up -d --build
sudo docker compose ps
curl http://localhost:8000/health
```

로그 확인:

```bash
cd ~/BE
sudo docker compose logs --tail=100 api
sudo docker compose logs --tail=100 postgres
sudo docker compose logs --tail=100 redis
```

서버의 `.env`와 로컬 SSH 키는 Git에 포함되지 않습니다.
