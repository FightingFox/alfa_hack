FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_CERT=/etc/ssl/certs/ca-bundle.pem

COPY ca-bundle.pem /etc/ssl/certs/ca-bundle.pem
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY scan.py .
COPY data_type.py .
COPY models.py .
COPY address_book.py .
COPY BASE/ BASE/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]