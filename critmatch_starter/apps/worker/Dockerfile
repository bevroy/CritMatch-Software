FROM python:3.12-slim

WORKDIR /app

# Install worker deps
COPY apps/worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Bring in the API package so the worker can reuse models/services
COPY apps/api /app/api_app
COPY apps/worker /app

ENV API_APP_PATH=/app/api_app
ENV PYTHONPATH=/app/api_app

CMD ["python", "app/main.py"]
