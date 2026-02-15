FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY . .

RUN uv sync --frozen --no-dev

CMD ["uv", "run", "python", "-m", "apps.bot_api.main"]
