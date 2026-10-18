# One image for all six services; the command picks the service.
# Runs as a non-root, arbitrary UID so it works under OpenShift's restricted SCC.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ASHGROVE_DATA_DIR=/data

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . \
 && mkdir -p /data \
 && chgrp -R 0 /data /app \
 && chmod -R g=u /data /app

USER 1001
EXPOSE 8000
ENTRYPOINT ["ashgrove", "serve"]
CMD ["crm", "--port", "8000"]
