# Solon — Underwriting Platform (demo)

Upload startup materials (pitch deck PDF, optional SOC 2 PDF, optional GitHub URL) and run a multi-source extraction pipeline: structured fields, reconciliation, rules-based scoring, and review UI—with confidence and citations where configured.

## Architecture

- **Next.js 14** (TypeScript, App Router, Tailwind CSS) — frontend + API routes
- **Python 3.11 + FastAPI** — AI extraction service and Temporal client endpoints
- **PostgreSQL 16 + pgvector** — submissions, profiles, audit events, document chunks
- **Temporal** — durable workflow orchestration (Docker Compose in dev)
- **Docker Compose** — Postgres, Temporal server, Temporal UI

## Quick Start

### 1. Start infrastructure

```bash
docker compose up -d
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env: OPENAI_API_KEY, DATABASE_URL if not using defaults
```

### 3. Start the AI service

```bash
cd ai
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8081
```

### 4. Start the Temporal worker (multi-source pipeline)

From `ai/`:

```bash
python -m workflows.worker
```

### 5. Start the Next.js app

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Use **Submit** for the full pipeline or legacy flows as implemented in the API.

## API Endpoints (representative)

| Endpoint | Method | Description |
|---|---|---|
| `/api/submissions` | POST | Create submission, attach sources, start workflow |
| `/api/extract` | POST | Legacy single PDF → `risk_profiles` |
| `/api/profiles` | GET | List risk profiles |
| `/api/health` | GET | App + DB health |
| `http://localhost:8081/extract` | POST | AI extraction (internal) |
| `http://localhost:8081/health` | GET | AI service health |

Temporal UI (dev): [http://localhost:8233](http://localhost:8233)
