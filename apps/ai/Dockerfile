FROM python:3.13-slim

WORKDIR /ai

# LightGBM·XGBoost는 OpenMP 런타임(libgomp1)이 필요하지만 slim 이미지에는 없습니다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 1. uv 설치 (공식 이미지에서 복사해오는 가장 깔끔한 방법)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 2. 의존성 패키지 관리 파일을 컨테이너 내부에 복사합니다.
COPY pyproject.toml uv.lock ./

# 3. pyproject.toml에 명시된 의존성 패키지를 설치합니다(dev 그룹 제외).
#    pyproject.toml에 별도 의존성 그룹이 없으므로 --group 옵션을 쓰지 않습니다.
RUN uv sync --no-dev --frozen

# 4. 로컬 소스 코드를 컨테이너 내부로 복사합니다.
#    data/, artifacts/, tests/는 .dockerignore로 제외합니다. 모델 번들은 실행 시 볼륨으로 마운트합니다.
COPY . .

# 로그를 버퍼 없이 바로 출력하고, 가상환경의 python을 기본으로 사용합니다.
ENV PYTHONUNBUFFERED=1 \
    PATH="/ai/.venv/bin:$PATH"

# 5. AI Worker를 실행합니다.
#    python을 직접 실행해 docker stop의 SIGTERM이 Worker에 바로 전달되도록 합니다(처리 중인 메시지를 마치고 종료).
CMD ["python", "main.py"]
