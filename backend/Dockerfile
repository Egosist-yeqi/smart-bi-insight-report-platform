FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app
ARG INSTALL_TORCH=false

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt
RUN if [ "$INSTALL_TORCH" = "true" ]; then pip install --no-cache-dir -r requirements-ml.txt; fi

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY tests ./tests
COPY entrypoint.sh ./entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
