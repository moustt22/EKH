# Enterprise Knowledge Hub

Permission-aware internal knowledge platform. This repository currently contains the runnable backend skeleton: FastAPI, PostgreSQL, Redis, Qdrant, MinIO, and a Celery worker.

## Run

Docker Compose is the supported way to start the stack.

```bash
docker compose up --build
```

On startup the API applies migrations and seeds six departments, three roles, and three local users. Every demo account uses the password `ChangeMe123!`.

| Email | Role | Department |
|---|---|---|
| admin@northwind.example | administrator | Management |
| eng.employee@northwind.example | employee | Engineering |
| hr.manager@northwind.example | department_manager | HR |

```bash
curl -s http://localhost:8000/auth/login -H "Content-Type: application/json" -d "{\"email\":\"admin@northwind.example\",\"password\":\"ChangeMe123!\"}"
```

The API then serves:

- http://localhost:8000/health
- http://localhost:8000/health/ready
- http://localhost:8000/docs

The React app is at http://localhost:5173. Load the fictional library with `python scripts/load_dataset.py`. The click-through is in `DEMO.md`.

MinIO console: http://localhost:9001 (`ekh` / `ekhsecret`). The `ekh-documents` bucket is created on startup.

Copy `.env.example` to `.env` when you add an OpenRouter key. Compose reads `OPENROUTER_API_KEY` and `LANGSMITH_API_KEY` from the shell or from a `.env` file in this directory. Set `LANGSMITH_TRACING=true` to record assistant traces with the model name and source document ids.

Administrators can read `GET /audit`. The local evaluation report is written with:

```bash
python -m app.evaluation.run
```

Local database credentials in Compose are for development only. Change `JWT_SECRET` before any shared deployment.

## Hosted pieces

Three outside services can replace parts of Compose. Redis, Qdrant, and the API still need a machine that stays running.

- **Neon** replaces Postgres. Put its connection string in `DATABASE_URL` and keep the `postgresql+psycopg` prefix, with `?sslmode=require` on the end.
- **Backblaze B2** replaces file storage. Create a private bucket, then set `MINIO_ENDPOINT` to the bucket’s S3 endpoint, `MINIO_REGION` to that endpoint’s region (for example `us-west-004`), `MINIO_SECURE=true`, and the application key as the access key and secret.
- **Vercel** publishes the website. Import the repo, set the root directory to `frontend`, and set `VITE_API_URL` to the public API address before the build. Add that Vercel address to `CORS_ORIGINS` on the API.

After changing `.env`, run `docker compose up -d api worker`. Login stays in this app. Clerk and Resend are not connected.

## Layout

```text
app/api          HTTP routes
app/core         settings
app/database     SQLAlchemy models and sessions
app/ingestion    document extraction and chunking
app/retrieval    permission-aware search
app/workflows    LangGraph assistant
app/evaluation   labeled questions and local scores
app/services     application services
app/workers      Celery tasks
```
