# syntax=docker/dockerfile:1.7

FROM python:3.14-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.14-slim AS runtime

RUN groupadd -r app && useradd -r -g app -u 10001 -m -d /home/app app

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=app:app . .

USER app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

CMD ["python", "main.py", "--env", "prod"]
