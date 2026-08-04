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

# PATCHED (audit fix, low): run as a non-root user instead of the base
# image's default root.
RUN groupadd --system critmatch \
	&& useradd --system --gid critmatch --home /app critmatch \
	&& chown -R critmatch:critmatch /app /app/api_app
USER critmatch

CMD ["python", "app/main.py"]
