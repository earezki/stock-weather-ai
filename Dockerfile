
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1 \
	PIP_DISABLE_PIP_VERSION_CHECK=1 \
	POETRY_VIRTUALENVS_CREATE=false \
	APP_HOME=/app

WORKDIR ${APP_HOME}

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		build-essential \
		curl \
		gnupg \
		ca-certificates \
		libnss3 \
		libatk1.0-0 \
		libatk-bridge2.0-0 \
		libcups2 \
		libxkbcommon0 \
		libgbm1 \
		libgtk-3-0 \
		libasound2 \
		libpangocairo-1.0-0 \
		libxss1 \
		fonts-noto-color-emoji \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN python -m pip install --upgrade pip setuptools wheel \
	&& pip install --no-cache-dir -r requirements.txt

RUN python -m playwright install --with-deps

COPY . ${APP_HOME}

RUN useradd -m appuser || true \
	&& chown -R appuser:appuser ${APP_HOME}
USER appuser

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
