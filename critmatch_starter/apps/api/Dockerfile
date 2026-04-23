FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x ./entrypoint.sh
ENV PORT=10000
EXPOSE ${PORT}
CMD ["./entrypoint.sh"]
