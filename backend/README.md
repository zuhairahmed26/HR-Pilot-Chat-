# HR Pilot — standalone backend

Standalone backend for the Cohere and Groq HR Pilot prototype. The original HR Pilot project stays unchanged. This prototype uses its own PostgreSQL, Redis, and Qdrant instances. The React frontend lives in `../frontend`.

## Implemented
- Login API `POST /api/hr/auth/login` using form-urlencoded `username` (email) and `password`; 24h JWT, account status checks
- `GET /api/hr/auth/employees/current_employee`
- Authenticated chat `POST /api/hr/chat/get_response` with multipart fields `user_query`, optional `session_id`, `provider` (`cohere` or `groq`), `chat_history` (accepted for request-shape compatibility but not trusted), `stream_events`, and an optional OPD `attachment`
- Selected-model intent classification on every message. There is no local intent shortcut. Active drafts are context for the classifier.
- Policy answers and general chat stream from the selected provider. With `stream_events=true`, SSE emits `status`, `chunk`, `done`, and `error` as content arrives.
- Cohere and Groq share one bounded history: the latest twelve user and assistant messages.
- Leave details are extracted by Cohere on every turn. Local date or reason patterns are not used. The employee must confirm before a pending leave row is stored.
- OPD amount, treatment date, and description are interpreted by the selected model on every turn. A new PNG or JPEG uses that provider's vision model. PDF text and typed details use text extraction.
- History: `GET /api/hr/chat/all`, `GET/PATCH/DELETE /api/hr/chat/{session_id}`, cache expiration endpoints
- Admin PDF upload `POST /api/hr/policy_vector_store/upload` and list/delete APIs
- Private local PDF storage, PyMuPDF extraction, Cohere Embed 5 Pro, Qdrant cosine search, and source references on policy answers
- PostgreSQL is the durable source of truth for messages. Redis stores a cache copy of the active session.

## NOT implemented (do not assume full parity)
- No Odoo/payroll or live HR transactions; unsupported payroll intents return explicit unsupported messages
- No Azure blob: private local files instead
- Leave-detail extraction always calls Cohere, even when `provider=groq`
- No OCR for scanned or image-only policy PDFs; no DOCX
- This is not the original HR Pilot intent schema or subworkflow orchestration
- No production Alembic migrations, robust rate limit, distributed task queue, or concurrency locking: **local prototype only**
- Original HR Pilot `/download_salary_slip/{token}` is not implemented

## Windows setup (PowerShell)
1. Open PowerShell in this `backend` directory (keep your `.venv`).
2. Install dependencies and create `.env`:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

3. Edit `.env`: set the standalone PostgreSQL password, a freshly generated SECRET_KEY, `COHERE_API_KEY`, and `GROQ_API_KEY`. Ports default to PostgreSQL 55432, Redis 56379, Qdrant 16333. Make sure all three containers are running. Do NOT point at your original HR database. `GROQ_MODEL` is optional; the client default is `qwen/qwen3.8-27b`.
4. Initialize the isolated schema and seed a synthetic admin:

```powershell
python -m scripts.init_db
python -m scripts.seed_employee --email admin@example.com --name "Test Admin" --role admin
```

5. Start API:

```powershell
python -m uvicorn src.main:app --reload --port 8001
```

6. Open `http://127.0.0.1:8001/docs` and test login. Use Swagger **Authorize** with username/password. Upload a text-based policy PDF via Policies > upload, then use chat > get_response.

### PowerShell login + chat test
```powershell
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8001/api/hr/auth/login -ContentType 'application/x-www-form-urlencoded' -Body @{username='admin@example.com';password='YOUR_TEST_PASSWORD'}
$token = $login.access_token
curl.exe -N -X POST http://127.0.0.1:8001/api/hr/chat/get_response -H "Authorization: Bearer $token" -F "user_query=What is the annual leave policy?" -F "stream_events=true"
```

### Data model
- `employees`: isolated synthetic users and login fields
- `hr_chathistory`: per-user session messages, titles, pinned status
- `policy_documents`: original PDF file paths + ingestion metadata
- Qdrant collection `policy_collection` dimension **2048**, generated with `input_type=search_document`; queries use `search_query`.

### Notes
- Input PDFs are stored in `storage/policies` with randomized safe filenames; that directory is gitignored and not statically served.
- `POST /get_response` requires authenticated bearer token. New session ID is returned in `X-Chat-Session-ID` header and SSE done payload.
- Existing `chat_history` form field is accepted for API compatibility, but authoritative saved history is read from PostgreSQL to prevent spoofing.
- Before external exposure add Alembic migrations, rate limits, concurrency control, ingestion cleanup/retry, and more rigorous policy access authorization.
- Seed data is synthetic, not copied from the original HR Pilot.
