# AI Healthcare Project Template

건강 정보를 입력하면 당뇨병·고혈압 위험도와 주요 원인을 예측하고, 결과에 맞는 건강 챌린지를 추천하는 서비스 템플릿입니다.
FastAPI API 서버, AI 추론 Worker, React 프론트엔드로 구성되며 `uv`와 `Docker Compose`로 개발·실행 환경을 맞춥니다.

---

## 🚀 주요 특징

- **FastAPI**: 비동기 API 서버. Router · Service · Repository 계층 구조
- **AI Worker**: KNHANES(국민건강영양조사) 기반 위험도 모델 추론을 API 서버와 분리된 프로세스에서 처리
- **Redis Stream · SSE**: 예측 요청을 Worker에 전달하고, 결과를 SSE로 실시간 전달
- **LLM 챌린지 추천**: 예측 위험도와 SHAP 요인을 바탕으로 Claude API가 챌린지를 추천
- **Tortoise ORM · Aerich**: 비동기 ORM과 마이그레이션
- **Docker Compose**: PostgreSQL, Redis, FastAPI, AI Worker, Nginx를 한 번에 실행
- **uv**: 앱별 `pyproject.toml`·`uv.lock`으로 의존성 버전 고정

---

## 📂 프로젝트 구조

```text
.
├── apps/
│   ├── ai/                     # AI 모델 학습 파이프라인 + 추론 Worker
│   │   ├── core/               # Worker 설정, 로거
│   │   ├── tasks/              # Redis Stream 메시지 계약·소비·예측 처리
│   │   ├── src/
│   │   │   ├── components/     # 데이터 로드·라벨·전처리·분할·학습·평가·SHAP 컴포넌트
│   │   │   └── pipelines/      # 학습·튜닝·평가·서빙 번들·추론 파이프라인
│   │   ├── tests/
│   │   ├── data/               # KNHANES 원시·가공 데이터 (Git 제외)
│   │   ├── artifacts/          # 모델·보고서 (Git 제외)
│   │   ├── main.py             # Worker 진입점
│   │   └── pyproject.toml, uv.lock
│   ├── backend/                # FastAPI 서버
│   │   ├── app/
│   │   │   ├── apis/v1/        # API 라우터
│   │   │   ├── core/           # 설정, DB, 예외 처리, LLM 클라이언트, Redis 등 공통 기능
│   │   │   ├── dependencies/   # 인증 등 의존성 주입
│   │   │   ├── models/         # DB 테이블 정의 (Tortoise)
│   │   │   ├── repositories/   # DB·캐시 접근
│   │   │   ├── schemas/        # 요청·응답 스키마 (Pydantic)
│   │   │   └── services/       # 비즈니스 로직
│   │   ├── migrations/         # Aerich 마이그레이션
│   │   ├── templates/          # 이메일 템플릿
│   │   ├── tests/
│   │   ├── main.py             # FastAPI 애플리케이션 진입점
│   │   └── pyproject.toml, uv.lock
│   └── frontend/               # React + Vite + TypeScript
│       └── src/                # pages, shared(api·components), styles
├── docs/                       # API 명세(api_spec/), AI 파이프라인 재현 가이드, 분석·모델 문서
├── envs/                       # 환경 변수 예시 파일
├── infra/nginx/                # Nginx 설정 (리버스 프록시)
├── scripts/                    # 배포 및 CI용 쉘 스크립트
├── docker-compose.yml          # 로컬 개발용 전체 스택 실행 설정
└── docker-compose.prod.yml     # 배포용 실행 설정
```

> 프로젝트 루트에는 `pyproject.toml`이 없습니다. Python 의존성은 `apps/backend`, `apps/ai`에서 각각 관리합니다.

---

## ⚙️ 사전 준비 사항

- **Python**: 3.13 이상
- **uv**: Python 패키지 매니저 ([설치 가이드](https://docs.astral.sh/uv/getting-started/installation/))
- **Node.js**: 프론트엔드 실행용 (`npm` 포함)
- **Docker & Docker Compose**: 전체 서비스 실행용

---

## 🛠️ 설치 및 설정

### 1. 의존성 설치

Backend와 AI는 각자의 디렉터리에서 설치합니다. `--frozen`은 `uv.lock`에 고정된 버전 그대로 설치합니다.

```bash
cd apps/backend
uv sync --frozen

cd ../ai
uv sync --frozen
```

프론트엔드는 `package-lock.json` 기준으로 설치합니다.

```bash
cd apps/frontend
npm ci
```

### 2. 환경 변수 설정

`envs/`의 예시 파일을 복사한 뒤, 프로젝트 루트에 `.env`를 만듭니다. `docker compose`와 프론트엔드(Vite) 모두 루트의 `.env`를 읽으므로 반드시 있어야 합니다.

macOS · Linux

```bash
cp envs/example.local.env envs/.local.env
ln -s envs/.local.env .env
```

Windows (PowerShell)

```powershell
Copy-Item envs/example.local.env envs/.local.env
Copy-Item envs/.local.env .env
```

> Windows에서 복사한 `.env`는 링크가 아닙니다. `envs/.local.env`를 수정했다면 마지막 명령을 다시 실행하세요.

배포용은 `envs/example.prod.env`를 `envs/.prod.env`로 복사해 사용합니다.

`envs/.local.env`에서 아래 항목을 확인합니다.

| 항목 | 설명 |
|---|---|
| `DB_HOST`, `REDIS_HOST` | Docker Compose로 실행할 때는 컨테이너 서비스 이름인 `postgres`, `redis`를 사용합니다. 예시 파일의 `DB_HOST=localhost`는 `postgres`로 바꿔야 FastAPI 컨테이너가 DB에 접속합니다. 컨테이너 밖에서 서버를 직접 실행할 때만 `localhost`를 씁니다. |
| `DB_PORT` | PostgreSQL 포트 `5432` |
| `SMTP_*` | 회원가입 시 인증 메일을 보냅니다. 예시 값으로는 메일이 발송되지 않아 가입할 수 없으므로, Gmail 주소와 [앱 비밀번호](https://myaccount.google.com/apppasswords)를 입력합니다. |
| `ANTHROPIC_API_KEY` | 챌린지 추천용 Claude API 키. 비워 두면 위험도 예측은 동작하고 챌린지 추천만 `LLM_NOT_CONFIGURED`로 실패합니다. 나중에 키를 등록하면 실패한 추천이 다시 생성됩니다. 실제 키는 커밋하지 않습니다. |
| `VITE_BACKEND_URL` | 프론트엔드가 호출할 API 주소. Nginx를 거치면 `http://localhost` |

### 3. AI 모델 서빙 번들 준비

AI Worker는 시작할 때 `apps/ai/artifacts/models/knhanes_serving/`의 서빙 번들을 읽습니다. 번들은 Git에 포함되지 않으므로 KNHANES 원시 데이터로 직접 만듭니다.

1. KNHANES 2020~2024 기초자료(`hn20_all.sas7bdat` ~ `hn24_all.sas7bdat`)를 `apps/ai/data/raw/knhanes/`에 저장합니다. 파이프라인은 이 5개 연도를 기준으로 작성되어 있어 파일이 하나라도 없거나 다른 연도를 넣으면 오류로 종료합니다. 연도를 바꾸려면 `apps/ai/src/knhanes_merge_configs.py`, `apps/ai/src/knhanes_split_configs.py`의 연도 설정과 연도별 변수 처리 규칙을 함께 수정합니다.
2. [AI 파이프라인 실행·재현 가이드](docs/ai_pipeline_reproduction.md)의 순서대로 `apps/ai`에서 파이프라인을 실행합니다.

번들이 없으면 Worker는 종료 코드 1로 끝나고, 3회 재시작 후 멈춥니다(`docker ps -a`에서 `Exited (1)`).

---

## 🏃 실행 방법

### 1. 로컬 및 개발 환경

#### Docker Compose로 전체 스택 실행

PostgreSQL, Redis, FastAPI, AI Worker, Nginx를 한 번에 실행합니다. FastAPI 컨테이너는 시작할 때 마이그레이션(`aerich upgrade`)을 먼저 적용합니다.

```bash
docker compose up -d --build
docker ps
```

- **Swagger UI**: [http://localhost/api/docs](http://localhost/api/docs) (Nginx 80 포트 경유)
- **FastAPI 직접 접속**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

코드를 수정한 서비스만 다시 빌드하려면 서비스 이름을 지정합니다.

```bash
docker compose up -d --build fastapi
docker compose up -d --build ai-worker
```

#### 프론트엔드 실행

```bash
cd apps/frontend
npm run dev
```

브라우저에서 [http://localhost:5173](http://localhost:5173)으로 접속합니다.

#### 포트 충돌

로컬에 PostgreSQL(5432)이나 Redis(6379)가 이미 실행 중이면 컨테이너가 시작되지 않습니다. 포트를 점유한 프로세스를 찾아 종료한 뒤 `docker compose up -d`를 다시 실행합니다.

```bash
# macOS · Linux
sudo lsof -nP -iTCP:5432 -sTCP:LISTEN
sudo lsof -nP -iTCP:6379 -sTCP:LISTEN
# -9는 강제 종료 신호입니다. "kill 9"처럼 -를 빼면 9번 프로세스에 신호를 보내게 됩니다.
sudo kill -9 <PID>
```

```powershell
# Windows (PowerShell)
netstat -ano | findstr :5432
netstat -ano | findstr :6379
taskkill /PID <PID> /F
```

#### Windows에서 Nginx가 실행되지 않는 경우

`infra/nginx/default.conf`는 `prod_http.conf`를 가리키는 심볼릭 링크입니다. Windows에서 Git이 링크를 일반 파일로 체크아웃하면 파일 내용이 `prod_http.conf` 한 줄만 남아, Nginx가 `nginx: [emerg] unexpected end of file` 오류로 종료됩니다.

```powershell
# 오류 확인
docker compose ps -a
docker compose logs --tail 100 nginx

# default.conf 내용이 prod_http.conf 한 줄뿐이라면 로컬 테스트용으로 설정 파일을 복사한 뒤 다시 실행
Copy-Item .\infra\nginx\prod_http.conf .\infra\nginx\default.conf -Force
docker compose up --build -d nginx
```

> 이 복사본은 로컬 테스트용 변경이므로 커밋하지 않습니다.

### 2. EC2 배포 환경 (Production)

제공된 쉘 스크립트를 사용하여 AWS EC2 환경에 이미지를 빌드, 푸시 및 배포할 수 있습니다.

#### 사전 준비
- EC2 인스턴스 (Ubuntu 권장)
- SSH 키 페어 (`~/.ssh/` 경로에 위치)
- 도커 허브(Docker Hub) 계정 및 Personal Access Token
- 배포용 환경 변수 설정 (`envs/.prod.env`)
- 도메인 구매 (Gabia, GoDaddy, AWS Route53 등)

#### 자동 배포 스크립트 실행
`scripts/deployment.sh`는 도커 이미지 빌드, 레포지토리 푸시, EC2 접속 및 컨테이너 실행 과정을 자동화합니다.

```bash
chmod +x scripts/deployment.sh
./scripts/deployment.sh
```
스크립트 실행 시 다음 정보를 입력해야 합니다:
1. 도커 허브 계정 정보 (Username, PAT)
2. 이미지를 업로드할 레포지토리 이름
3. 배포할 서비스 선택 (FastAPI, AI-Worker) 및 버전(Tag)
4. SSH 키 파일명 및 EC2 IP 주소
5. https 사용여부
   - 5-1. https인 경우 도메인 추가 입력

AI Worker를 배포할 때는 서빙 번들도 서버에 함께 준비해야 합니다.

#### SSL(HTTPS) 설정 (Certbot)
도메인을 연결하고 HTTPS를 적용하려면 `scripts/certbot.sh`를 사용합니다.

```bash
chmod +x scripts/certbot.sh
./scripts/certbot.sh
```
1. 도메인 주소 및 이메일 입력
2. SSH 키 파일명 및 EC2 IP 주소 입력
3. Let's Encrypt를 통한 인증서 발급 및 Nginx 설정 자동 갱신 적용

---

## 🧪 테스트 및 품질 관리

`scripts/ci/`의 스크립트는 `apps/backend`를 대상으로 실행됩니다. Backend 테스트는 PostgreSQL이 실행 중이어야 합니다(`docker compose up -d postgres`). Redis는 테스트에서 가짜 객체(fakeredis)로 대체됩니다.

```bash
# Backend 테스트 + 커버리지
./scripts/ci/run_test.sh

# Backend 코드 포맷팅·린트 자동 수정 (Ruff)
./scripts/ci/code_fommatting.sh

# Backend 정적 타입 검사 (Mypy)
./scripts/ci/check_mypy.sh
```

Windows에서 Backend 테스트 중 `ZoneInfoNotFoundError: 'No time zone found with key Asia/Seoul'`이 나면, 의존성 파일을 고치지 말고 `apps/backend`에서 실행할 때만 시간대 데이터를 추가합니다.

```powershell
uv run --with tzdata python -m pytest -x -vv --tb=short
```

AI와 프론트엔드는 각 디렉터리에서 실행합니다.

```bash
# AI
cd apps/ai
uv run pytest
uv run ruff check . && uv run ruff format --check .

# Frontend
cd apps/frontend
npm run lint
```

GitHub Actions(`.github/workflows/checks.yml`)는 Backend·AI·Frontend 린트와 Backend 테스트를 실행합니다.

---

## 📝 개발 가이드

- **API 추가**: `apps/backend/app/apis/v1/`에 라우터를 만들고 `apps/backend/app/apis/v1/__init__.py`의 `v1_routers`에 등록합니다. 비즈니스 로직은 `services/`, DB 접근은 `repositories/`에 둡니다. 명세는 `docs/api_spec/`에 함께 작성합니다.
- **DB 모델 추가**: `apps/backend/app/models/`에 Tortoise 모델을 정의하고 `apps/backend/app/core/db/databases.py`의 `TORTOISE_APP_MODELS`에 추가한 뒤, `apps/backend`에서 `uv run aerich migrate --name <설명>`으로 마이그레이션을 만듭니다.
- **AI 로직 추가**: 학습·전처리 로직은 `apps/ai/src/components/`, 실행 순서는 `apps/ai/src/pipelines/`에 둡니다. Worker가 처리하는 메시지는 `apps/ai/tasks/`에서 정의합니다. 라벨을 만드는 데 쓴 검사값(당뇨: 공복혈당·당화혈색소, 고혈압: 혈압)과 진단 여부는 해당 질환 모델의 입력에 넣지 않습니다(데이터 누수).
- **프론트엔드 API 연결**: API 호출은 `apps/frontend/src/shared/api/`에 두고 공통 `request<T>`(`client.ts`)를 사용합니다. 예측 결과 SSE는 인증 헤더가 필요해 브라우저 `EventSource`를 쓸 수 없으므로, `diseasePredictionApi.ts`의 `waitForPredictionResult`(내부적으로 `fetch` 스트리밍)를 사용합니다.
