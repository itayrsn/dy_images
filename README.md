# Image Search Platform – Architecture Plan

## Objectives
- Provide a modular, containerised baseline that covers the full image search lifecycle: ingestion → embedding → vector search → user query experience.
- Optimise for clarity, reproducibility, and extensibility so new team members can contribute quickly.
- Surface operational considerations (observability, failure handling, scaling) that demonstrate production-minded thinking.

## High-Level Data Flow

```text
URL dataset ─┐
             ├─▶ Image Downloader ─▶ /data/images volume
             │
             └─▶ (future) incremental URL feeder

/data/images ─▶ Embedding Worker ─▶ /data/artifacts
                                          ├─ embeddings.npy
                                          ├─ faiss.index
                                          └─ metadata.jsonl

/data/artifacts ─▶ Vector API ─┬─▶ REST search endpoint (/search)
                               └─▶ Health/metrics (/health, /metrics)

Vector API ─▶ UI service ─▶ Browser
```

Shared Docker volumes:
- `images_data`: raw images downloaded once and reused.
- `artifacts_data`: manifests, embeddings, FAISS index, metadata catalogue.

## Services and Responsibilities

### 1. Image Downloader (current focus)
- Asynchronous downloader (`aiohttp` + bounded concurrency).
- Idempotent: URL dedupe, cache detection, resumable via manifest (`manifest.jsonl`).
- Emits rich telemetry (status, latency, bytes, content-type) for downstream monitoring.
- Exposed via CLI (`typer`) to run as one-shot job or cron-like batch.
- Scaling: run multiple containers with sharded URL lists; push manifest into message queue (e.g., Redis Streams) for incremental embedding jobs.

### 2. Embedding Worker
- Loads CLIP/BLIP vision-language model (default: `openai/clip-vit-base-patch32` via `open_clip` or `sentence-transformers`).
- Processes new images detected in manifest (skips cached ones).
- Generates embeddings in batches, persists to `.npy` (float32) plus metadata describing image path, checksum, timestamps.
- Builds/updates FAISS index (`IndexIVFFlat` over cosine similarity) stored in `/data/artifacts/faiss.index`.
- Emits provenance to `artifacts_data/embedding_manifest.jsonl` (tracking versions, model hash).
- Scaling: support GPU workers; split workload using task queue; maintain incremental update pipeline.

### 3. Vector API Service
- FastAPI app that:
  - Loads FAISS index & metadata into memory on start.
  - Exposes `/search` (POST) accepting query text, returning top-K matches with scores and metadata.
  - Exposes `/ingest` (optional) to accept new embedding payloads for online updates.
  - Provides `/health` and `/metrics` (Prometheus) endpoints.
- Uses same embedding model for query text (share weights via common package).
- In-memory caching of recent query embeddings (LRU) to reduce recomputation.
- Scaling: horizontal auto-scaling with shared artifact storage (S3, NAS) or remote vector DB (Milvus, Weaviate); for high QPS, switch to managed vector DB or replicate FAISS with sharded indices.

### 4. UI Service
- Lightweight frontend (FastAPI + HTMX or React) container.
- Renders search bar, hits Vector API, displays results grid.
- Handles progressive loading, basic analytics (search latency, zero-hit rate).
- Production readiness: integrate CDN for static assets, add auth if required.

## Common Python Package (`/shared_lib`)
- House reusable modules:
  - `config.py`: environment-driven settings (12-factor).
  - `models.py`: CLIP wrapper, embedding utilities.
  - `storage.py`: manifest readers/writers.
- Each service copies/installs package to ensure consistent embedding logic.
- Enables unit testing outside containers.

## Docker Compose Topology

```yaml
services:
  downloader:
    build: ./image_downloader
    volumes:
      - images_data:/data/images
      - ./image_downloader/image_urls.txt:/data/input/image_urls.txt:ro
      - artifacts_data:/data/artifacts
    command: ["run", "--output-dir", "/data/images", "--manifest-path", "/data/artifacts/manifest.jsonl"]

  embedder:
    build: ./embedding_service
    volumes:
      - images_data:/data/images:ro
      - artifacts_data:/data/artifacts
    environment:
      - MODEL_NAME=openai/clip-vit-base-patch32

  vector_api:
    build: ./vector_service
    ports:
      - "8000:8000"
    volumes:
      - artifacts_data:/data/artifacts:ro

  ui:
    build: ./ui_service
    ports:
      - "3000:3000"
    environment:
      - VECTOR_API_URL=http://vector_api:8000

volumes:
  images_data:
  artifacts_data:
```

Networking: default Docker network with service discovery (`vector_api` hostname accessible within UI container). Volumes ensure clear separation between raw images and derived artefacts.

## Observability, Testing, and DX
- Structured logging (JSON logs optional) with correlation IDs per request/job.
- Metrics: Prometheus counters/gauges for download success ratio, embedding throughput, query latency.
- Health checks: `docker-compose` `healthcheck` for each container (e.g., downloader exit code, embedder heartbeat, API `/health`).
- Testing: unit tests for shared libs; smoke tests for downloader (mocked `aiohttp` server), integration tests using sample dataset.
- Developer tooling: `Makefile` or `./scripts/bootstrap.sh` to build images, run compose, seed dataset. Pre-commit hooks for formatting (`ruff`, `black`), type-checking (`mypy`) to be added progressively.

## Scaling Strategy for Millions of Images
- **Ingestion:** partition URL feed (Kafka topic or SQS queue); stateless downloader workers consuming partitions; store manifests in object storage (S3) with metadata DB (PostgreSQL) tracking status.
- **Embeddings:** move to GPU-enabled AutoScaling groups; batch size tuned per GPU memory; maintain rolling model versions with feature flags; incremental FAISS index updates or swap to distributed vector DB (Milvus, Pinecone, Weaviate). Snapshot artefacts to S3, load via lazy mmap to reduce startup time.
- **Vector Search:** for high QPS, shard index by semantic buckets or use hierarchical navigable small world graphs (HNSW) via Milvus/Weaviate; enable replication for read scaling; use CDN caching for hot queries.
- **UI/API:** horizontally scale behind load balancer (e.g., Nginx/Envoy); implement request-level caching (Redis) for recent queries; apply rate limiting/auth.
- **Resilience:** adopt circuit breakers for third-party calls, retries with exponential backoff, and dead-letter queues for failed downloads.

## Next Implementation Steps
1. Finalise shared library scaffolding and configuration schema.
2. Implement embedding worker (PyTorch + CLIP) with batch job control.
3. Build Vector API (FastAPI) with FAISS integration + tests.
4. Craft UI service (FastAPI+Jinja/HTMX) and wire to API.
5. Assemble docker-compose, ensure reproducible `make dev` workflow.
6. Document setup, execution, troubleshooting, and scaling narrative.

This plan keeps the MVP focused while showcasing production-minded design, leaving clear hooks for advanced features (authentication, analytics, auto-tagging, background refresh).*** End Patch

