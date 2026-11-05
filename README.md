# Enterprise Knowledge Hub

Permission-aware knowledge app for the fictional company Northwind. People can search and ask questions only against documents they are allowed to read. The model never decides access.

The running pieces are:

| Piece | Where it runs |
|---|---|
| Website | Vercel, from the `frontend` directory |
| API, worker, Redis, and Qdrant | Docker on a computer that stays on |
| Postgres | Neon, or the local Postgres container |
| Files | Backblaze B2, or the local file container |
| Chat and embeddings | OpenRouter |

The current public site is https://frontend-iota-black-73.vercel.app. It calls an API tunnel on the operator's computer. If that computer sleeps, the site still opens and sign-in fails until the tunnel is started again.

## Accounts

Every demo account uses the password `ChangeMe123!`. These users are created when `ENVIRONMENT=local`.

| Email | Role | Department |
|---|---|---|
| admin@northwind.example | administrator | Management |
| eng.employee@northwind.example | employee | Engineering |
| hr.manager@northwind.example | department_manager | HR |

The administrator sees every document, can upload to any department, and can delete any document. The administrator also has People and Audit.

The HR manager can upload and delete only HR documents. The engineer can read Engineering documents and cannot upload or delete.

A department document is readable by an administrator, its owner, or a person in that department. A restricted document is readable by an administrator, its owner, or someone on its grant list. Grants are added on the document page by email.

Uploads accept PDF and DOCX. After upload the file stays on "processing" until indexing finishes, then it can be searched.

## Run on one machine

Install Docker. Copy `.env.example` to `.env` and set `OPENROUTER_API_KEY`. Compose reads that file.

```bash
docker compose up --build
```

- Website: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Local file console: http://localhost:9001 (`ekh` / `ekhsecret`)

Load the handbooks:

```bash
python scripts/load_dataset.py
```

The click-through is in `DEMO.md`. Administrators can read `GET /audit`. A local score report is written with:

```bash
python -m app.evaluation.run
```

Set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` to record assistant traces. Change `JWT_SECRET` before anyone else can open the site. Do not commit `.env`.

The chat model is `openrouter/free`. Embeddings use `openai/text-embedding-3-small` at 1536 dimensions. Changing the embedding model requires a new index and another load of the library.

## Library

`python scripts/load_dataset.py` replaces any document with the same title. The seven handbooks are:

| Document | Readers |
|---|---|
| Salary bands | HR |
| Leave policy | HR |
| On-call guide | Engineering |
| Office hours | Engineering |
| Expense policy | Finance |
| Discount authority | Sales |
| Vendor intake | Operations |

There is no Finance, Sales, or Operations demo user, so those three handbooks are visible to the administrator.

## Publish the website

The website is a Vite app. Vercel builds `frontend` and rewrites every path to `index.html`. Set `VITE_API_URL` to the public API address before the build. The value is baked into the site, so a new API address needs a new deploy.

From `frontend`, after `npx vercel login`:

```bash
npx vercel deploy --prod --yes --build-env VITE_API_URL=https://your-api-host
```

Put that same site origin in `CORS_ORIGINS`, then recreate the API:

```bash
docker compose up -d --force-recreate --no-deps api
```

## Keep the public API up

Neon and Backblaze replace the local database and file server. Redis, Qdrant, the API, and the worker still run in Docker. Start only those:

```bash
docker compose up -d redis qdrant api worker
```

In `.env`:

- `DATABASE_URL` is the Neon string with the prefix changed to `postgresql+psycopg://` and `?sslmode=require` on the end.
- `MINIO_ENDPOINT` is the Backblaze S3 host, without `https://`. `MINIO_REGION` is the region in that host, such as `us-east-005`. `MINIO_SECURE=true`. The access key and secret are a Backblaze application key for a private bucket.
- `JWT_SECRET` is a long random string.
- `CORS_ORIGINS` includes the Vercel site origin.
- `OPENROUTER_API_KEY` is set.

A free tunnel publishes the API while this computer stays on:

```bash
cloudflared tunnel --url http://localhost:8000
```

Copy the `https://….trycloudflare.com` address into `VITE_API_URL` and deploy the website again. The address changes every time the tunnel starts. A dead tunnel makes sign-in show "Failed to fetch".

Login stays in this app. Clerk and Resend are not connected.

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
frontend         React website
scripts          fictional library loader
```
