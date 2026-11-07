# Enterprise Knowledge Hub

Enterprise Knowledge Hub (EKH) is a personal, public-demo RAG application for
asking grounded questions about company documents. It is built around a simple
rule:

> The model may write the answer, but it never decides what the user is allowed
> to retrieve.

The application supports PDF and DOCX uploads, asynchronous indexing, permission-
aware search, cited answers, conversation history, document sharing, audit events,
and deterministic RAG regression tests.

## Public demo

- Website: https://frontend-iota-black-73.vercel.app
- Local website: http://localhost:5173
- Local API: http://localhost:8000
- API documentation: http://localhost:8000/docs

The public demo intentionally uses fictional Northwind documents and sample
accounts. These accounts are for demonstration only:

| Account | Role | Department |
|---|---|---|
| `admin@northwind.example` | Administrator | Management |
| `hr.manager@northwind.example` | Department manager | HR |
| `eng.employee@northwind.example` | Employee | Engineering |

The local/demo password is `ChangeMe123!`. Do not reuse it for a real deployment.

## What the demo proves

The demo contains seven fictional handbooks:

| Document | Owning team | Demo readers |
|---|---|---|
| Leave Policy | HR | HR manager, administrator |
| Salary Bands | HR | HR manager, administrator |
| Office Hours | Engineering | Engineer, administrator |
| On-Call Guide | Engineering | Engineer, administrator |
| Expense Policy | Finance | Administrator |
| Discount Authority | Sales | Administrator |
| Vendor Intake | Operations | Administrator |

The same document can belong to multiple teams. Existing document grants are
also supported for sharing a document with a specific user.

## Architecture

```text
Browser
  |
  v
React/Vite frontend
  |
  v
FastAPI API ---- PostgreSQL/Neon: users, metadata, chunks, conversations, audits
  |       \
  |        \---- Qdrant: dense and sparse chunk vectors
  |
  \---- Redis/Celery: asynchronous ingestion jobs
  |
  \---- Backblaze B2/MinIO: original PDF and DOCX files
  |
  \---- OpenRouter: embeddings and chat completion
```

### Retrieval and answer flow

1. Authenticate the user.
2. Rewrite only short follow-up questions; complete questions are searched
   verbatim so previous turns cannot contaminate unrelated questions.
3. Generate dense and sparse query representations.
4. Search Qdrant using user and department filters.
5. Re-check every candidate against PostgreSQL access rules.
6. Retrieve current-version chunks from active documents.
7. Ask the chat model to answer only from the retrieved passages.
8. Reject malformed, empty, instruction-like, or uncited answers.
9. Return citations containing document, page, version, and copied evidence.
10. Store the question, answer, citations, and audit metadata.

Access filtering is applied in SQL listing, document download, Qdrant filtering,
in-memory test indexing, and final retrieval validation.

## Storage responsibilities

| Data | Store |
|---|---|
| Users, roles, departments | PostgreSQL/Neon |
| Document metadata and versions | PostgreSQL/Neon |
| Extracted chunks | PostgreSQL/Neon |
| Conversations, citations, audit events | PostgreSQL/Neon |
| Dense and sparse embeddings | Qdrant collection `ekh_chunks` |
| Original files | Backblaze B2 or local MinIO |
| Embedding model | `openai/text-embedding-3-small`, 1536 dimensions |
| Chat model | `google/gemini-2.5-flash-lite` through OpenRouter |

Embeddings are not stored in Neon. Changing the embedding model requires
re-embedding the documents and rebuilding the Qdrant collection.

## Run locally

### Requirements

- Docker Desktop
- Python 3.11+ for local scripts/tests
- Node.js 20+ for frontend development
- An OpenRouter API key for live embeddings and chat

### Start the stack

```powershell
Copy-Item .env.example .env
# Set OPENROUTER_API_KEY in .env
docker compose up --build
```

Services:

- Website: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001

The API runs migrations and seeds demo users when `ENVIRONMENT=local`.

### Load the fictional library

```powershell
python scripts/load_dataset.py
```

The loader replaces documents with matching titles, uploads generated PDFs, and
writes the generated IDs to `dataset/manifest.json`. The manifest is generated
runtime data and is not required in source control.

### Run the frontend separately

```powershell
Set-Location frontend
npm install
npm run dev
```

### Run tests and evaluation

```powershell
$env:PYTHONPATH='.'
pytest -q
python -m app.evaluation.run
Set-Location frontend
npm run build
```

## Upload behavior

The upload flow intentionally avoids confusing internal classification controls.
Users provide:

- File
- Optional document name
- One or more owning teams

New uploads use internal, owning-team visibility by default. Filename-derived
titles are used when no name is supplied. Documents remain `processing` until
Celery finishes extraction, chunking, embedding, and indexing. Failed jobs can
be retried from the document page.

The older classification and restricted-access fields remain in the data model
only for backward compatibility with existing documents and grant workflows.
They are not part of the normal upload experience.

## Access rules

- Administrators can read and manage all active documents.
- A document owner can read their document.
- Department documents are readable by users in any owning department.
- Explicit user grants can add read access outside the owning department.
- Access is checked again when downloading a source file.
- Search results never expose inaccessible documents.
- Conversations belong to their creating user.

## Evaluation results

### Deterministic regression suite

The current deterministic dataset contains ten cases covering:

- Vacation accrual
- Paid holidays
- Salary-band access
- Engineering office hours
- SEV1 incident response
- Expense receipts
- Discount approvals
- Vendor approvals
- Unsupported questions
- Prompt injection in a document

Current baseline from `python -m app.evaluation.run`:

| Metric | Result | Meaning |
|---|---:|---|
| Faithfulness | **1.0000** | Answer claims are supported by supplied evidence |
| Answer relevance | **0.9509** | Token-level F1 against expected answers |
| Citation accuracy | **1.0000** | Citation passages are contained in retrieved evidence |

These are deterministic assistant-pipeline metrics. They are a regression gate,
not proof that live Qdrant retrieval or the external model is perfect.

### Live questions and observed answers

The following live tests were run using the indexed Northwind PDFs and the
public API.

#### Engineer conversation

**Question:** When are Engineering core hours?

**Observed answer:** Engineering core hours are 10:00 to 16:00 in the employee's
local time. During core hours, engineers answer messages within two hours and
attend scheduled meetings. Outside core hours, there is no response expectation
except for the on-call engineer.

**Result:** Pass. Cited `Office Hours`, page 1.

**Question:** What should happen for a severity one production incident?

**Observed answer:** A SEV1 is a full outage or data loss affecting most
customers, or a security breach. The first responder acknowledges within five
minutes, posts updates every 30 minutes, and a postmortem is written within five
business days of resolution.

**Result:** Pass. Cited `On Call Guide`, pages 1 and 3.

**Question:** How many vacation days do employees accrue?

**Observed answer:** The documents you can access do not contain enough
information to answer that.

**Result:** Pass. The engineer cannot access HR's Leave Policy.

#### HR manager conversation

**Question:** How many vacation days do employees accrue after 3 years of service?

**Observed answer:** Employees with 3 to less than 6 years of service accrue 20
vacation days per year, equivalent to 0.833 days per semi-monthly pay period.

**Result:** Pass. Cited `Leave Policy`, page 1.

**Question:** How many paid holidays does Northwind observe each year?

**Observed answer:** Northwind observes 11 paid holidays annually, including the
listed company holidays, with nearest-weekday observation for weekend holidays
and compensatory time for on-call or customer-coverage staff.

**Result:** Pass. Cited `Leave Policy`, page 2.

**Question:** What is the salary band for a senior engineer?

**Observed answer:** For the E3 Senior Software Engineer in a Tier 3 location:

- Minimum: $124,000
- Midpoint: $145,000
- Maximum: $174,000

**Result:** Pass. Cited `Salary Bands`, page 1.

### Live evaluation targets

For a release candidate, measure the real indexed documents and external model
with this matrix:

| Metric | Target |
|---|---:|
| Retrieval hit rate | >= 90% |
| Answer correctness | >= 90% |
| Citation correctness | >= 95% |
| Access-control accuracy | 100% |
| Unsupported-question refusal | >= 95% |
| Ingestion success | >= 95% |

Also record median and p95 answer latency, provider errors, queue depth, and
OpenRouter cost. A fluent answer from the wrong department is a failure even if
the wording looks correct.

## Production and public-demo hardening

The public demo intentionally runs in `ENVIRONMENT=local`, which seeds sample
accounts. A real shared deployment must use `ENVIRONMENT=production` and:

1. Rotate every credential ever exposed in chat, logs, screenshots, or commits.
2. Generate a random `JWT_SECRET` of at least 32 bytes.
3. Set `MINIO_SECURE=true` and use private object storage.
4. Remove localhost entries from `CORS_ORIGINS`.
5. Provide `OPENROUTER_API_KEY`.
6. Do not seed demo users or reuse `ChangeMe123!`.
7. Configure `OPENROUTER_CHAT_FALLBACK_MODEL` if a backup model is approved.
8. Keep rate limiting enabled.
9. Restrict production database, Qdrant, Redis, and object-storage networks.
10. Add provider spend limits and alerts.

The API has bounded model retries and optional fallback behavior. The current
single-instance limiter is enabled in the demo with:

```env
RATE_LIMIT_ENABLED=true
LOGIN_RATE_LIMIT=10
API_RATE_LIMIT=60
RATE_LIMIT_WINDOW_SECONDS=60
```

For multiple API instances, replace the in-process limiter with Redis or an API
gateway limiter.

Back up and periodically restore all three data layers together:

- Neon/PostgreSQL
- Backblaze B2 source files
- Qdrant vectors

A restore is incomplete if metadata and source files return but Qdrant vectors
are missing. Monitor `/health/ready`, ingestion failures, queue depth, provider
errors, latency, and model spend. Reconcile active PostgreSQL documents against
current Qdrant points after migrations or recovery.

## Repository layout

```text
app/
  api/          FastAPI routes and dependency guards
  core/         settings, roles, security, document constants
  database/     SQLAlchemy models, sessions, demo seed
  evaluation/   deterministic dataset, runner, scoring
  ingestion/    extraction, chunking, embeddings, pipeline
  retrieval/    permission-aware search
  schemas/      API request/response models
  services/     access, chat, documents, storage, vectors, users, audit
  workers/      Celery application, tasks, queue helpers
  workflows/    assistant graph, prompts, tracing
frontend/
  src/          React pages, components, API client, auth
alembic/
  versions/     database migrations
scripts/
  load_dataset.py
tests/
  test_*.py     backend regression and security tests
```

## Key commands

```powershell
# Start local demo
docker compose up --build

# Load fictional documents
python scripts/load_dataset.py

# Run backend tests
$env:PYTHONPATH='.'
pytest -q

# Run deterministic evaluation
python -m app.evaluation.run

# Build frontend
Set-Location frontend
npm run build
```

## Known boundaries

- The live benchmark is manual; the deterministic runner does not call OpenRouter.
- The single-instance rate limiter is not a distributed limiter.
- OCR for image-only PDFs is not implemented.
- Backups and restore drills must be configured at the hosting-provider level.
- The public API depends on the operator's computer/tunnel unless deployed to a
  persistent API host.
