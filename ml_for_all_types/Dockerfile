FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_CERT=/etc/ssl/certs/ca-bundle.pem

COPY ca-bundle.pem /etc/ssl/certs/ca-bundle.pem
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "ws_server:app", "--host", "0.0.0.0", "--port", "8000"]