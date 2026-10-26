# HR Pilot Cohere — standalone backend (v0.1)

Standalone **backend implementation**, not a finished identical HR Pilot frontend. Original project stays unchanged. New prototype uses its own PostgreSQL/Redis/Qdrant instances.

## Implemented
- Login API `POST /api/hr/auth/login` using form-urlencoded `username` (email) and `password`; 24h JWT, account status checks
- `GET /api/hr/auth/employees/current_employee`
- Authenticated chat POST `/api/hr/chat/get_response` with multipart fields `user_query`, optional `session_id`, `chat_history` (accepted for request-shape compatibility but not trusted), `stream_events`
- History: `GET /api/hr/chat/all`, `GET/PATCH/DELETE /api/hr/chat/{session_id}`, cache expiration endpoints
- Admin PDF upload `POST /api/hr/policy_vector_store/upload` and list/delete APIs
- Private local PDF storage, PyMuPDF extraction, Cohere Embed 5 Pro, Qdrant cosine search, Cohere Command A+ policy answers with source references
- PostgreSQL is the durable source of truth for messages; Redis is an optional cache

## NOT implemented (do not assume full parity)
- No Odoo/payroll or live HR transactions; such intents return explicit unsupported messages
- No Azure blob: private local PDFs instead
- No independent replica frontend yet
- Chat is **NOT token-streamed**: raw and SSE responses are supported, but the complete Cohere answer is sent as one chunk
- No OCR for scanned/image-only PDF; no DOCX; no model-based 11-intent structured classifier; no original HR Pilot subworkflow orchestration
- PDF upload endpoints are new simplified endpoints; verify frontend adaptation later
- No production Alembic migrations, robust rate limit, distributed task queue, or concurrency locking: **local prototype only**
- Original HR Pilot `/download_salary_slip/{token}` is not implemented

## Windows setup (PowerShell)
1. Extract project into `C:\Users\zuhai\Desktop\HR Pilot\app_v2` (keep your `.venv`).
2. Open PowerShell there:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

3. Edit `.env`: set the standalone PostgreSQL password, a freshly generated SECRET_KEY, and COHERE_API_KEY. Ports default to PostgreSQL 55432, Redis 56379, Qdrant 16333. Make sure all three containers are running. Do NOT point at your original HR database.
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
