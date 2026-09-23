FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_CERT=/etc/ssl/certs/ca-bundle.pem

WORKDIR /app

COPY ca-bundle.pem /etc/ssl/certs/ca-bundle.pem
COPY pyproject.toml ./
COPY app ./app
COPY run.py ./

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["python", "run.py"]