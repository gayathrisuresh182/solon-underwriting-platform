# Mini Hammurabi — AI Startup Risk Extraction Engine

Upload a startup pitch deck PDF and get structured risk fields extracted by GPT-4o, scored, and displayed in a review dashboard with confidence levels.

## Architecture

- **Next.js 14** (TypeScript, App Router, Tailwind CSS) — frontend + API routes
- **Python 3.11 + FastAPI** — AI extraction service
- **PostgreSQL 16** — stores extraction results
- **Docker Compose** — PostgreSQL only (dev mode)

## Quick Start

### 1. Start PostgreSQL

```bash
docker compose up -d
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 3. Start the AI extraction service

```bash
cd ai
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8081
```

### 4. Start the Next.js app

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to use the dashboard.

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/extract` | POST | Upload PDF, trigger AI extraction |
| `/api/profiles` | GET | List all risk profiles |
| `/api/profiles?id=<uuid>` | GET | Get single profile with overrides |
| `/api/health` | GET | Health check |
| `localhost:8081/extract` | POST | AI extraction service (internal) |
| `localhost:8081/health` | GET | AI service health check |
