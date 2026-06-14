FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

COPY core/requirements.txt /tmp/requirements.txt
RUN grep -Ev '^#|^\s*$' /tmp/requirements.txt > /tmp/requirements.runtime.txt \
    && pip install --no-cache-dir -r /tmp/requirements.runtime.txt

EXPOSE 8000

CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000"]
