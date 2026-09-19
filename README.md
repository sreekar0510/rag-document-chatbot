# RAG Document Chatbot

A portfolio-grade, full-stack Retrieval-Augmented Generation (RAG) chatbot that lets you upload documents (PDF, TXT), ask questions, and receive answers grounded in your documents with source citations.

**Stack:** React · Vite · TypeScript · FastAPI · ChromaDB · sentence-transformers · Amazon Bedrock

---

## Architecture

```
Browser (React + Vite)
        │  HTTP / SSE
        ▼
FastAPI REST API  (port 8000)
        │
        ├─ Document ingestion  → text extraction → chunking
        ├─ Embedding service   → sentence-transformers (local)
        ├─ Vector store        → ChromaDB
        ├─ Retrieval service   → similarity search
        └─ Generation service  → Amazon Bedrock (Claude via Converse API)
```

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Python | ≥ 3.11 |
| Node.js | ≥ 20 |
| npm | ≥ 10 |
| AWS credentials | configured via env / IAM role |

### 1 — Clone & configure

```bash
git clone <repo-url>
cd rag-document-chatbot
cp .env.example backend/.env   # fill in your values
```

### 2 — Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start development server
uvicorn app.main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/api/health`

### 3 — Frontend

```bash
cd frontend
npm install
npm run dev                     # starts on http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`.

---

## Available Scripts

### Backend (`backend/`)

| Command | Description |
|---------|-------------|
| `uvicorn app.main:app --reload` | Start dev server |
| `pytest` | Run all tests |
| `pytest tests/test_health.py` | Run a single test file |
| `pytest -k test_health_returns_ok` | Run a single test by name |

### Frontend (`frontend/`)

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server |
| `npm run build` | Production build |
| `npm run lint` | ESLint |
| `npm run typecheck` | TypeScript type-check (no emit) |

---

## Project Structure

```
rag-document-chatbot/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/        # FastAPI routers (health, documents, chat …)
│   │   ├── core/
│   │   │   ├── config.py      # Pydantic-settings configuration
│   │   │   ├── logging.py     # Structured logging (structlog)
│   │   │   └── middleware.py  # Request-ID middleware
│   │   ├── models/            # Pydantic request/response schemas
│   │   ├── services/          # Business logic (ingestion, retrieval, generation)
│   │   └── main.py            # Application factory
│   ├── tests/
│   ├── requirements.txt       # Stage-1 deps (FastAPI, uvicorn, structlog …)
│   ├── requirements-full.txt  # Future deps (boto3, chromadb, sentence-transformers …)
│   └── pytest.ini
├── frontend/
│   ├── src/
│   │   ├── App.tsx            # Application shell
│   │   └── main.tsx           # React entry point
│   ├── public/
│   ├── vite.config.ts
│   └── package.json
├── .env.example
├── .dockerignore
└── README.md
```

---

## Configuration

All settings live in [`backend/app/core/config.py`](backend/app/core/config.py) and are read from environment variables / `.env`.  See [`.env.example`](.env.example) for the full list.

**AWS credentials are NEVER hardcoded.**  Use:
- Local development: `~/.aws/credentials` or exported shell vars
- Production: IAM instance profile / ECS task role

---

## Roadmap

- [x] Stage 1 — Project scaffold, health endpoint, frontend shell
- [ ] Stage 2 — PDF/TXT ingestion, text extraction, chunking
- [ ] Stage 3 — Embeddings (sentence-transformers) + ChromaDB
- [ ] Stage 4 — Retrieval service, similarity search
- [ ] Stage 5 — Amazon Bedrock generation (Converse / ConverseStream)
- [ ] Stage 6 — Chat API, streaming, source citations
- [ ] Stage 7 — Document listing & deletion
- [ ] Stage 8 — Docker, Docker Compose, Nginx, HTTPS
- [ ] Stage 9 — AWS ECR / EC2 deployment

---

## Security

- AWS credentials are read exclusively from the environment — never stored in code or config files.
- The frontend never receives AWS credentials.
- Credentials are never logged.
- `.env` is git-ignored.
