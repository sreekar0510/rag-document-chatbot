# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Stack
- **Backend**: Python 3.11+ · FastAPI · Pydantic v2 · pydantic-settings · structlog
- **Frontend**: React 18 · Vite 6 · TypeScript (strict) · ESLint flat config
- **Future stages**: sentence-transformers (local embeddings) · ChromaDB · Amazon Bedrock (Converse/ConverseStream API)

## Commands

### Backend (`cd backend` first, activate `.venv`)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # dev server
pytest                                       # all tests
pytest tests/test_health.py                 # single file
pytest -k test_health_returns_ok            # single test by name
```

### Frontend (`cd frontend` first)
```bash
npm install
npm run dev          # Vite dev server on :5173 (proxies /api → :8000)
npm run build        # production build → dist/
npm run typecheck    # tsc --noEmit (no emit)
npm run lint         # eslint --max-warnings 0
```

## Architecture
- `backend/app/main.py` — application factory (`create_app()`); `app` instance used by uvicorn
- `backend/app/core/config.py` — single `Settings` class (pydantic-settings); always import via `get_settings()` (lru_cache)
- `backend/app/core/logging.py` — structlog; call `configure_logging()` once in `create_app()`; use `get_logger(__name__)` everywhere else
- `backend/app/core/middleware.py` — `RequestIDMiddleware` injects `X-Request-ID` into every request/response
- `backend/app/api/routes/` — one file per domain (health, documents, chat …); register via `app.include_router(router, prefix=settings.api_prefix)`
- Vite dev server proxies `/api/*` to `http://localhost:8000` — no CORS issues during local development

## Critical conventions

### Python
- All modules start with `from __future__ import annotations`
- Use `from app.core.config import get_settings` (never instantiate `Settings()` directly)
- Use `get_logger(__name__)` from `app.core.logging`, not the stdlib `logging` module directly
- AWS credentials: read exclusively from env / IAM role — never hardcode, never log, never send to frontend
- Pydantic v2 syntax throughout (`.model_config`, `model_dump()`, not `.dict()`)

### TypeScript / React
- Strict TypeScript — `noUnusedLocals`, `noUnusedParameters`, `noUncheckedSideEffectImports` all enabled
- ESLint is configured with `--max-warnings 0`; zero warnings allowed in CI
- `tsconfig.json` is a project-references wrapper; app code lives in `tsconfig.app.json`, Vite config in `tsconfig.node.json`

## Adding new routes (backend)
1. Create `backend/app/api/routes/<domain>.py` with an `APIRouter`
2. Register in `backend/app/main.py` inside `create_app()` with `app.include_router(..., prefix=settings.api_prefix)`

## Adding new services (backend)
- Place business logic in `backend/app/services/<service>.py`
- Models (request/response schemas) go in `backend/app/models/`

## Environment / secrets
- Copy `.env.example` → `backend/.env` for local dev
- The `backend/.env` file is git-ignored — never commit it
- `ALLOWED_ORIGINS` is a JSON-encoded list, e.g. `["http://localhost:5173"]`
