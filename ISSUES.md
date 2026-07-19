# Phase 1 Review — Issues Found in the Original Project

Source reviewed: `D:\fyp\uoj_chatbot\uoj_chatbot` (Django + DRF, OpenAI + ChromaDB + LlamaIndex RAG
pipeline). Each issue below lists what was found, its root cause, and how the new project
(`umt_chatbot_groq`) addresses it. Issues are grouped by severity.

## Critical (security)

### 1. Real secrets hardcoded in tracked source
`uoj_chatbot/settings.py` had literal values for `OPENAI_API_KEY`, `SECRET_KEY`,
`EMAIL_HOST_PASSWORD` (a Gmail app password), and the Google OAuth client secret — even though
the same file also loads `.env` a few lines later and re-reads `SECRET_KEY`/`OPENAI_API_KEY` from
it. The hardcoded values were the actual working credentials, just duplicated into source that
git tracks.
- **Root cause**: values were pasted directly during early development and never removed once
  `.env` loading was added.
- **Fix**: `umt_chatbot_groq/settings.py` reads every secret exclusively from `.env` (raises at
  startup if `SECRET_KEY` is missing); `.env.example` ships with blank placeholders; `.env` is
  gitignored.
- **Action needed from you**: rotate the OpenAI key, Django secret key, and Gmail app password
  that were exposed in the old repo's history — they must be treated as compromised.

### 2. Admin/document-management endpoints had no authentication
`upload_document`, `check_status`, `delete_uploaded_file`, `chroma_list_docs`, and `upload_list`
in the old `chatbot/views.py` had no `permission_classes` or auth requirement at all (several were
also `@csrf_exempt`). Anyone who could reach the API could inject arbitrary content into the
knowledge base (a direct prompt-injection / data-poisoning vector) or wipe it via delete.
- **Root cause**: these endpoints were built and never had auth wired in.
- **Fix**: `chatbot/views/documents.py` requires `JWTAuthentication` + `IsAdminUser` (staff) on
  every document-management endpoint.

### 3. Insecure CORS/CSRF defaults
`CORS_ALLOW_ALL_ORIGINS = True` was combined with `CORS_ALLOW_CREDENTIALS = True` (any site can
make credentialed requests), and `CSRF_COOKIE_SECURE = False` with `CSRF_COOKIE_SAMESITE = "None"`.
- **Fix**: explicit `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` allow-lists driven by env vars;
  `CSRF_COOKIE_SECURE` / `SESSION_COOKIE_SECURE` now follow `DEBUG`.

### 4. Exception detail leaked to API clients
`ask_query`, `ContactUsView`, and `update_user` (and others) returned `str(e)` directly in the
JSON response body on unhandled exceptions.
- **Fix**: all new views log the exception server-side (`logger.exception(...)`) and return a
  generic, safe message to the client.

## High (correctness)

### 5. Background RAG path was crashing
`chatbot/background_task.py::generate_answer_sync` and `chatbot/views.py::background_rag` both
called `get_chatgpt_response(query, context)` — 2 positional arguments — but
`get_chatgpt_response(user_query: str) -> str` only accepted one. Any query that took the
authenticated/background path (not the cache-hit or anonymous-with-cached-answer paths) would
raise `TypeError` at runtime.
- **Root cause**: `get_chatgpt_response` was refactored to do its own retrieval internally, but
  the two call sites that used to pass pre-fetched context were never updated.
- **Fix**: one function, `generate_rag_response(query)` (`chatbot/utils/rag.py`), with a single
  signature used by every call site.

### 6. ChromaDB deletes were silent no-ops
`process_uploaded_file()` wrote node metadata as `{filename, file_hash, file_type}` — no
`document_id` key — but `delete_uploaded_file()` called
`chroma_collection.delete(where={"document_id": uploaded.file_hash})`. Since no node ever had a
`document_id` field, the delete matched nothing: removing a file from the admin panel left its
embedded chunks permanently searchable in the vector store.
- **Fix**: `chatbot/utils/ingestion.py` now stamps `document_id=file_hash` on every node's
  metadata at ingestion time, so the existing delete-by-metadata call actually matches.

### 7. Duplicate retrieval per query
`search_chromadb_context()` ran a retrieval pass just to check "is there any context for this
query", then `get_chatgpt_response()` ran a second, independent retrieval pass to actually build
the prompt — doubling embedding/vector-store calls (and latency) on every non-cached question.
- **Fix**: `retrieve_context()` in `chatbot/utils/rag.py` runs once per query; its result is reused
  both for the existence check and for building the prompt.

## Medium (maintainability / dead code)

### 8. Dead code not carried forward
- `chatbot/signals.py` — entirely commented out (~300 lines), an abandoned earlier
  implementation of the same ingestion pipeline.
- `chatbot/utils/university_check.py::is_university_related` — imported in `views.py` but only
  ever called from commented-out lines.
- `chatbot/utils/chatgpt_response.py::query_index` — defined, never called anywhere.
- `chatbot/utils/add_to_chroma_vector_db.py` — defined, never called anywhere.
- `views.py` re-imported the same names (e.g. `Notification`, `NotificationSerializer`,
  `IsAuthenticated`) three to four times at different points in a single ~1250-line file.

None of the above exist in the new project.

### 9. Redundant embedding configuration
`embedding_setup.py` configured both a raw `OpenAIEmbeddingFunction` (for direct
`chroma_collection.add()` calls) and `LlamaSettings.embed_model` (for LlamaIndex-driven inserts) —
two independent configurations that had to be kept in sync by hand and could silently drift.
- **Fix**: both are still required (Chroma's native client and LlamaIndex each need their own
  embedding config), but the model name now comes from a single Django setting
  (`settings.EMBEDDING_MODEL`) so they can't diverge.

### 10. Inconsistent logging
Mixed `print()` and `logger.*` calls throughout, no log formatter (bare `StreamHandler`).
- **Fix**: consistent `logger.*` usage; `LOGGING` now has a formatter with timestamps and levels.

## Out of scope for this migration (dropped, by your decision)

The following modules existed in the original project but are not part of the RAG chatbot itself
and were dropped from `umt_chatbot_groq` per your "core chatbot only" scope decision: the admin
analytics dashboard (visitor/user/question stat charts, PDF report export via `xhtml2pdf`), the
notifications system, the feedback module, the contact-us form, OTP-based password reset, Google
OAuth login, profile picture uploads, and general user self-management CRUD. Their unused
dependencies (Celery, `social-auth-app-django`, `social-auth-core`, `xhtml2pdf`, `reportlab`,
`svglib`, `selenium`, `langchain`) were dropped from `requirements.txt` accordingly — Celery in
particular was installed in the original project but never actually wired up to any task queue
worker or `@shared_task`.

## Unchanged by design

Per your instructions, the RAG pipeline's *design* (chunking strategy, chunk size/overlap,
ChromaDB as the vector store, LlamaIndex as the indexing/retrieval layer) is untouched. See
`README.md` for what changed mechanically in `chatbot/utils/rag.py`.

## Addendum: embeddings also moved off OpenAI

After the plan above was approved, you asked to drop OpenAI entirely rather than just the LLM
step, since Groq is free/cheap and OpenAI billing was a concern. Groq has no embeddings API, so
`chatbot/utils/embedding_setup.py` now uses a free, local, open-source HuggingFace model
(`BAAI/bge-small-en-v1.5` via `sentence-transformers`, run on your machine's CPU) instead of
OpenAI's `text-embedding-3-small`. This is a provider swap, not a pipeline redesign — chunking,
ChromaDB storage, and LlamaIndex retrieval are unchanged; only which service computes the vectors
changed. Practical trade-offs versus the original OpenAI embeddings:
- **Cost**: zero — no API key, no per-token charge, runs locally.
- **First-run cost**: the model weights (~130MB for `bge-small-en-v1.5`) download once from the
  HuggingFace Hub and are cached under `~/.cache/huggingface`; subsequent runs are instant.
- **Quality**: `bge-small-en-v1.5` is a strong general-purpose retrieval model but is not identical
  to `text-embedding-3-small` — retrieval ranking may differ slightly. If you re-point this project
  at an existing ChromaDB built with OpenAI embeddings, you must re-index all documents (embeddings
  from different models are not comparable/interchangeable in the same collection).
- **Compute**: embedding runs on CPU by default; large bulk re-indexing jobs will be slower than an
  API call, though per-query embedding at chat time is fast enough not to be noticeable.
- Requirements now install `llama-index-embeddings-huggingface` and `sentence-transformers`
  (which pulls in `torch`) instead of `llama-index-embeddings-openai`.
