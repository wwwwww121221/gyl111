FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libreoffice \
        fonts-noto-cjk \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
COPY python_sdk_v8.2.0 ./python_sdk_v8.2.0
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
