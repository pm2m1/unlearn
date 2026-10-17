# Unlearn API: FastAPI + agents + static UI. Build from the repo root:
#   docker build -f api/Dockerfile -t unlearn-api .
# The embedding model and the pinned Eedi CSVs are baked in at build time, so a cold start needs no network
# for them; on first boot the app self-heals the graphs from those files.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface \
    PYTHONPATH=/app/api:/app

# The app runs as an unprivileged user that owns /app from the start (no chown -R layer duplicating files).
RUN useradd --create-home --uid 10001 unlearn && mkdir -p /app && chown unlearn /app
WORKDIR /app

# CPU-only torch: the default Linux wheel pulls ~2 GB of CUDA libraries the API never uses.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1
COPY requirements.txt .
RUN pip install -r requirements.txt

USER unlearn

# Bake the embedding model (all-MiniLM-L6-v2, 384-d) into the image.
COPY --chown=unlearn api/unlearn/embed.py /tmp/embed.py
RUN python -c "import sys; sys.path.insert(0, '/tmp'); from embed import MODEL; \
from sentence_transformers import SentenceTransformer; SentenceTransformer(MODEL, device='cpu')" \
 && rm /tmp/embed.py

COPY --chown=unlearn api ./api
COPY --chown=unlearn scripts ./scripts
COPY --chown=unlearn eval ./eval
COPY --chown=unlearn data/curated ./data/curated

# Bake the pinned Eedi CSVs (CC BY 4.0) so self-heal can seed without reaching Hugging Face.
RUN python scripts/01_download.py

# From here on the model and data come from the image only.
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["uvicorn", "main:app", "--app-dir", "api", "--host", "0.0.0.0", "--port", "8000"]
