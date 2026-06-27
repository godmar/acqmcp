FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ACQ_OPENAPI_PATH=/app/acq.json \
    BIBS_OPENAPI_PATH=/app/bibs.json

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY acq.json .
COPY bibs.json .
COPY src ./src
COPY pyproject.toml .
RUN pip install --no-cache-dir .

USER appuser
EXPOSE 8000

CMD ["uvicorn", "acqmcp.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
