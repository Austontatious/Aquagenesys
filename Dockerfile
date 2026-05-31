FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AQUAGENESYS_HOST=0.0.0.0 \
    AQUAGENESYS_PORT=8765 \
    AQUAGENESYS_DELIBERATION_ENABLED=false \
    AQUAGENESYS_MODEL_TEACHING_ENABLED=false \
    AQUAGENESYS_PUBLIC_DEMO=true \
    AQUAGENESYS_ARCHIVE_DIR=/tmp/aquagenesys-v03 \
    AQUAGENESYS_ARCHIVE_EVERY_TICKS=0 \
    AQUAGENESYS_LLM_BASE_URL=http://host.docker.internal:8008/v1 \
    AQUAGENESYS_LLM_MODEL=Lexi \
    AQUAGENESYS_LLM_TIMEOUT_SECONDS=30.0

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && adduser --disabled-password --gecos "" --uid 10001 aquagenesys

COPY . .
RUN chown -R aquagenesys:aquagenesys /app

USER aquagenesys

EXPOSE 8765

CMD ["python", "-m", "aquagenesys.web.app", "--host", "0.0.0.0", "--port", "8765"]
