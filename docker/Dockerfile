FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY requirements-inference.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-inference.txt


FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY src/ ./src/
COPY models/ ./models/

EXPOSE 8000

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
