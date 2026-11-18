# API image. Works for docker compose (port 8000) and Hugging Face Spaces (set PORT=7860 in the Space).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 app
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && python -m spacy download en_core_web_sm
ENV HF_HOME=/app/.cache FASTEMBED_CACHE_PATH=/app/.cache/fastembed PORT=8000
# Bake the CPU models into the image so a cold start does not download them.
RUN python -c "from fastembed import TextEmbedding; from fastembed.rerank.cross_encoder import TextCrossEncoder; \
TextEmbedding('BAAI/bge-small-en-v1.5'); TextCrossEncoder('BAAI/bge-reranker-base')"
COPY backend backend
COPY corpus corpus
COPY db db
COPY golden.jsonl golden.jsonl
RUN chown -R app /app
USER app
WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
