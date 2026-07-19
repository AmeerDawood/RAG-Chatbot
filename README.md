# UOJ Chatbot (Groq edition)

A standalone Django + DRF RAG chatbot for the University of Jhang, migrated off OpenAI entirely:
answer generation now calls **Groq**, and embeddings run on a **free, local, open-source
HuggingFace model** (no OpenAI API key, no per-call embedding cost). The retrieval *pipeline
design* — chunking strategy, ChromaDB as the vector store, LlamaIndex as the indexing/retrieval
layer — is unchanged from the original project; only the model providers behind embeddings and
generation moved. See `ISSUES.md` for the full Phase 1 review of the original project (issues
found, root causes, fixes applied here).

## Architecture

```
Documents (pdf/txt/docx/csv/xlsx)
        │  chatbot/utils/ingestion.py  (extract → clean → chunk)
        ▼
Local HuggingFace embeddings (BAAI/bge-small-en-v1.5)  ──►  ChromaDB
        │  chatbot/utils/embedding_setup.py
        ▼
LlamaIndex retriever  ──►  chatbot/utils/rag.py::retrieve_context()
        │
        ▼
Groq LLM (chatbot/utils/rag.py::generate_rag_response())  ──►  Answer
```

Both external-cost dependencies from the original project (OpenAI for embeddings, OpenAI for
generation) are gone. The only paid API in this stack is Groq, which has a free tier.

Project scope (per migration decision): core chatbot only — chat query, document
upload/ingestion/management, chat history, and the minimal auth needed to gate admin uploads and
attribute chat history to users. The original project's analytics dashboard, notifications,
feedback module, contact-us form, and self-service user management were out of scope and are not
part of this project.

## Project layout

```
uoj_chatbot_groq/       Django settings, root urls, asgi/wsgi
authenticate/           Minimal JWT auth (signup/login/token refresh), custom User (email login)
chatbot/
  models.py             ChatHistory, UploadedFile, AnonymousUserLog
  views/
    chat.py             /query/, chat history endpoints
    documents.py         /upload/ and related admin-only document management endpoints
  utils/
    embedding_setup.py   Chroma + local HuggingFace embeddings
    ingestion.py          Text extraction, cleaning, chunking, indexing
    rag.py                Single retrieval pass + Groq generation
  management/commands/clearcache.py
templates/               Minimal demo UI (query.html, upload.html) exercising the real APIs
ISSUES.md               Phase 1 review: issues, root causes, fixes
```

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/) via `pyproject.toml` (no manual
`requirements.txt`/venv juggling).

1. **Install dependencies** (creates `.venv` and `uv.lock` automatically)
   ```
   uv sync
   ```
   Run subsequent commands with `uv run ...` (e.g. `uv run python manage.py migrate`), or activate
   the environment yourself: `.venv\Scripts\activate` (Windows) / `source .venv/bin/activate`.

2. **Environment variables** — copy `.env.example` to `.env` and fill in:
   - `SECRET_KEY` — any long random string
   - `EMBEDDING_MODEL` — defaults to `BAAI/bge-small-en-v1.5`, runs locally, no API key
   - `GROQ_API_KEY` — used for answer generation ([console.groq.com](https://console.groq.com) has a free tier)
   - `GROQ_MODEL` — defaults to `llama-3.3-70b-versatile`
   - `REDIS_URL` — a running Redis instance is required for answer caching
   - `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` — your frontend's origin(s)

3. **Database & superuser**
   ```
   uv run python manage.py migrate
   uv run python manage.py createsuperuser
   ```
   The superuser (`is_staff=True`) is the account that can upload/delete documents.

4. **Run**
   ```
   uv run python manage.py runserver
   ```
   - Demo chat UI: `http://localhost:8000/demo/query/`
   - Demo upload UI (admin login required): `http://localhost:8000/demo/upload/`

## API summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/signup/` | none | Register |
| POST | `/auth/login/` | none | Get JWT access/refresh tokens |
| POST | `/auth/token/refresh/` | none | Refresh access token |
| GET  | `/auth/me/` | JWT | Current user |
| POST | `/query/` | optional JWT | Ask a question (RAG + Groq) |
| GET  | `/chat-response/<id>/` | JWT | Poll for a background-generated answer |
| GET  | `/chat-history/` | JWT | List chat history |
| DELETE | `/chat-history/<id>/` | JWT | Delete one chat entry |
| DELETE | `/chat-history/delete-all/` | JWT | Delete all (own, or all if staff) |
| POST | `/upload/` | JWT + staff | Upload a document for indexing |
| GET  | `/upload/status/<id>/` | JWT + staff | Check indexing status |
| GET  | `/upload/list/` | JWT + staff | List uploaded documents |
| DELETE | `/delete-file/<id>/` | JWT + staff | Delete a document and its vectors |
| GET  | `/chroma-list-docs/` | JWT + staff | Raw dump of indexed chunks |

## What changed vs. the original project (mechanically)

`chatbot/utils/rag.py` replaces `chatgpt_response.py` + `engine.py` +
`background_task.py::generate_answer_sync` with one function,
`generate_rag_response(query)`, that:
1. Retrieves context from the same Chroma/LlamaIndex index (`retrieve_context()`), once.
2. Builds the same system+user prompt used previously.
3. Calls `LlamaSettings.llm` — now a `llama_index.llms.groq.Groq` instance — via `.chat(...)`
   instead of a raw `requests.post()` to OpenAI's Chat Completions endpoint.

Retrieval, chunking, and embeddings are untouched.

## Verification steps

These require your own Groq API key and a running Redis instance:

1. `uv run python manage.py check` — should report no issues.
2. `uv run python manage.py migrate` — applies cleanly to a fresh `db.sqlite3`.
3. Register a user (`/auth/signup/`), promote it to staff via
   `uv run python manage.py createsuperuser` or the Django admin, then log in (`/auth/login/`).
4. Upload a small `.txt` file via `/upload/` (or `/demo/upload/`) as the staff user — confirm:
   - an anonymous request is rejected (401/403),
   - the staff request succeeds and `status` eventually becomes `success`.
5. Ask a question that matches the uploaded content via `/query/` (or `/demo/query/`) — confirm a
   Groq-generated answer referencing that content.
6. Delete the uploaded file via `/delete-file/<id>/`, ask the same question again — confirm the
   answer no longer reflects the deleted content (validates the ChromaDB delete fix in
   `ISSUES.md` #6).
7. Ask an unrelated/nonsense question — confirm the "not found" fallback response, not a crash.

I was not able to run steps 3–7 myself in this session — they require a live `GROQ_API_KEY` and a
running Redis server, which only you can supply. Steps 1–2 were run and verified during
development of this project.
