# Agora Backend

## API documentation

- Swagger UI: http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/openapi.json
- API base URL: http://localhost:8000

Docker Compose로 백엔드를 실행한 뒤 Swagger UI에서 API 명세를 확인하고 직접 요청을 테스트할 수 있습니다.

## Local run

```bash
docker compose up -d --build
docker compose ps
```

PostgreSQL과 Redis는 Docker 내부 네트워크에서만 접근할 수 있으며 FastAPI의 `${API_PORT:-8000}` 포트만 호스트에 공개됩니다.

## OCI hackathon deployment

이 배포 절차는 Ubuntu 기반 OCI Compute 인스턴스를 기준으로 합니다.

### 1. OCI network

인스턴스가 사용하는 VCN Security List 또는 Network Security Group의 ingress에 TCP `8000`을 추가합니다. SSH 접속을 위한 TCP `22`도 필요합니다. PostgreSQL `5432`와 Redis `6379`는 열지 않습니다.

### 2. Install Docker

Docker 공식 Ubuntu 저장소에서 Docker Engine과 Compose 플러그인을 설치하고 서비스를 활성화합니다.

```bash
sudo systemctl enable --now docker
docker version
docker compose version
```

### 3. Clone and configure

```bash
git clone https://github.com/TheZoneAgora/BE.git
cd BE
cp .env.example .env
```

`.env`에서 `POSTGRES_PASSWORD`를 임의의 긴 비밀번호로 교체하고, 프론트엔드가 사용하는 origin에 맞춰 `CORS_ORIGINS`를 수정합니다. `/agora` 같은 URL 경로는 CORS origin에 포함하지 않습니다.

```dotenv
POSTGRES_DB=agora
POSTGRES_USER=agora
POSTGRES_PASSWORD=replace_with_a_long_random_password
API_PORT=8000
CORS_ORIGINS=["http://localhost:3000"]
```

환경 변수 파일은 소유자만 읽을 수 있도록 설정합니다.

```bash
chmod 600 .env
```

### 4. Start and verify

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
```

정상 응답은 다음과 같습니다.

```json
{"status":"ok","database":"ok"}
```

외부에서는 다음 주소를 사용합니다.

- Swagger UI: `http://SERVER_PUBLIC_IP:8000/docs`
- Health check: `http://SERVER_PUBLIC_IP:8000/health`
- Agent registration: `POST http://SERVER_PUBLIC_IP:8000/agents`

### 5. Update

```bash
git pull --ff-only
docker compose up -d --build
docker compose ps
```

`restart: unless-stopped`가 모든 서비스에 적용되어 있어 Docker와 서버가 재시작된 뒤 컨테이너도 다시 실행됩니다.
