FROM python:3.13.1-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN groupadd --gid 10001 litflow \
    && useradd --uid 10001 --gid litflow --create-home --home-dir /home/litflow --shell /usr/sbin/nologin litflow

COPY requirements.runtime.lock pyproject.toml ./
RUN python -m pip install --no-cache-dir -r requirements.runtime.lock

COPY src ./src
RUN python -m pip install --no-cache-dir --no-build-isolation --no-deps . \
    && chown -R litflow:litflow /app

USER litflow

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=3s --start-period=10s --retries=3 CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2).read()"

CMD ["uvicorn", "litflow_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
