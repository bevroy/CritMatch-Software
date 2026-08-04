FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x ./entrypoint.sh
# PATCHED (audit fix, low): run as a non-root user instead of the base
# image's default root, as basic container-escape defense-in-depth.
RUN groupadd --system critmatch \
	&& useradd --system --gid critmatch --home /app critmatch \
	&& chown -R critmatch:critmatch /app
USER critmatch
ENV PORT=10000
EXPOSE ${PORT}
CMD ["./entrypoint.sh"]
