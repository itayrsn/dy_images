# DY Images – Image Search Platform

The DY Images repo contains a small, containerised platform that ingests image URLs, downloads raw assets, generates CLIP embeddings, stores them inside Qdrant, and exposes a Streamlit UI for natural‑language search.

## Quickstart
- Install Docker and Docker Compose v2.
- Populate `downloader/image_urls.txt` with the URLs you want to index.
- Build and run everything with `docker compose up --build`.
- Open http://localhost:8501 to access the Streamlit search UI once containers are healthy.

### Services
- `downloader`: async job that saves the URLs to a shared volume and publishes a message per downloaded file.
- `indexer`: consumes download messages, asks the embedding service for vectors, and upserts points into Qdrant.
- `embedding`: LitServe wrapper around OpenCLIP for both text and image embeddings.
- `app`: Streamlit UI that converts user text queries into embeddings and queries Qdrant for the top match list.
- `rabbitmq`, `qdrant`: infrastructure dependencies used for messaging and vector storage.

All Python services follow their own `pyproject.toml` (Python 3.13+ for the UI; 3.14+ for the workers) and are packaged with uv for reproducible installs.

## Architecture Snapshot

```text
image_urls.txt --> downloader --> RabbitMQ queue
                                     |
                                     v
                                 indexer --> Qdrant (images collection)
                        ^               \
                        |                -> embeds produced by embedding service
Streamlit UI --> text embedding --------/
```

- Raw images are kept on a Docker volume that is mounted into downloader, embedding, and app containers.
- Embedding calls are synchronous HTTP POSTs to `embedding/main.py` served through LitServe.
- Qdrant exposes HTTP on 6333 and gRPC on 6334; the app talks to it over HTTP.

## Local Development Tips
- Each service folder contains its own `.gitignore`, `.python-version`, and `pyproject.toml`.
- Use `uv sync` inside a service directory to create its virtual environment when running outside Docker.
- The `.vscode/launch.json` file contains launchers for Streamlit and every worker for easier debugging.
- Environment variables such as `RABBITMQ_HOST`, `QDRANT_HOST`, and `EMBEDDING_SERVICE_URL` can be overridden per service if you run components separately.

## Scaling & Production Considerations
- Run multiple downloader instances sharded by URL manifest to increase throughput.
- Move the embedding service to GPU hardware; LitServe already supports CUDA autocast, so only the Docker image needs NVidia tooling.
- Promote Qdrant to a managed cluster or replace it with Milvus when collections grow beyond a single node.
- Add Prometheus/Grafana for metrics, structured JSON logging for each service, and retries/backoff when calling downstream services.
- For the UI, put a CDN or cache in front of static assets and enforce auth/rate limiting when exposed publicly.

## Next Steps
1. Add automated tests for downloader/indexer logic (mocking RabbitMQ and embedding calls).
2. Provide a warmup script that seeds Qdrant with example data for demos.
3. Containerise a lightweight admin CLI for re-indexing or dropping collections on demand.
4. Record a quick Loom video demo once the dataset is populated.

Questions or ideas? Open an issue or drop a PR. Happy searching!
