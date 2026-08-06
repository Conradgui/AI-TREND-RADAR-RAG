FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY rag/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ChromaDB lazily downloads its default embedding model on the first write.
# Warm it during the visible Docker build instead of making a new user wait
# after the dashboard has already opened.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['warmup'])"

COPY . /app
RUN chmod +x /app/scripts/docker-entrypoint.sh

EXPOSE 8001

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
