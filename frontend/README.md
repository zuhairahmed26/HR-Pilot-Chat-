# HR Pilot AI — Frontend MVP

Responsive, standalone React + Vite + TypeScript UI for the HR Pilot backend. The chat can use Cohere or Groq.

## Run locally (Windows PowerShell)

In backend terminal:

```powershell
cd "C:\Users\zuhai\Desktop\HR Pilot\backend"
.\.venv\Scripts\Activate.ps1
python -m uvicorn src.main:app --reload --port 8001
```

On Windows, `backend\start.bat` can open the backend and frontend in separate windows after both are installed.

In a **separate** frontend terminal, from this frontend directory:

```powershell
cd "C:\Users\zuhai\Desktop\HR Pilot\frontend"
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. Log in with the existing backend employee email/password (`admin@example.com` if that is still your test account; use its actual password).

## How it connects

Vite proxies `/api/*` and `/health/*` to `http://127.0.0.1:8001`, avoiding browser CORS changes during local development. Do not browse directly to `8001` for the frontend. `VITE_API_BASE_URL` is optional for deployments; if set, configure the backend's CORS allowlist for the frontend origin. Do not put Cohere API keys or database secrets into the frontend.

The login call is `application/x-www-form-urlencoded` to `POST /api/hr/auth/login`. The chat uses multipart form data and real SSE events (`status`, `chunk`, `done`, `error`). The returned session ID is reused on subsequent messages. The server is the source of truth for history and any leave/ticket transactions. The UI only displays confirmation text; it never assumes a transaction occurred until the server reports it.

## Included

- Login/authentication and token handling (sessionStorage; re-login on expiration).
- Responsive desktop/mobile layout with sidebar and collapsible navigation.
- New chat, open history, rename, pin, delete, search.
- Incrementally rendered SSE chat responses, markdown, policy citations.
- Session-aware multi-turn HR requests (leave, ticket, and OPD confirmation).
- Cohere or Groq selection for a new chat. The choice is kept in the browser for that conversation.
- OPD slip attachment in chat (PDF, JPG, or PNG), plus a page for locally stored claims.
- Employee's locally stored leave requests and support tickets.
- Loading, empty, and network-error states.

## Important limitations

- The prototype stores the JWT in `sessionStorage` for convenience. For production, use a server-backed or HttpOnly cookie strategy and add comprehensive security hardening.
- The ticket/leave creation workflows depend on the existing backend; no Odoo actions are performed.
- Provider DNS or network failures remain a backend issue and appear in the chat as errors.
- Chat attachments are for OPD slips. HR policy PDFs are uploaded through the backend policy API, not this chat composer.
- This UI uses Google Fonts when available and falls back to local system fonts offline.

## Build check

```powershell
npm run build
```

For deployment, use a proper reverse proxy or set `VITE_API_BASE_URL` before build. For frontend local development leave it empty.
