# HR Pilot — Multi-Model AI Chatbot (Cohere & Groq)

A standalone AI-powered HR chatbot built using **FastAPI, React, Cohere, Groq, PostgreSQL, Redis, and Qdrant**.

This project is an independent prototype of the original HR Pilot Chat Module. It allows users to switch between Cohere and Groq for AI-powered conversations while demonstrating policy question answering, conversational memory, and selected HR workflows.

**Project scope:** This is a standalone MVP for evaluating alternative LLM providers. It is not intended to replace the complete original HR Pilot application.

## 1. Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend | Python, FastAPI |
| LLM Provider 1 | Cohere — Command A+ |
| LLM Provider 2 | Groq — Qwen |
| Embeddings | Cohere Embed 5 Pro |
| Vector Database | Qdrant |
| Relational Database | PostgreSQL |
| Cache | Redis |
| Authentication | JWT |
| Document Processing | PyMuPDF |

## 2. Project Structure

```text
HR-Pilot-Chat/
├── backend/
│   ├── src/
│   │   ├── core/
│   │   │   ├── cohere_client.py
│   │   │   ├── groq_client.py
│   │   │   └── llm_router.py
│   │   ├── hr_management_agent/
│   │   │   ├── chat/
│   │   │   ├── leave/
│   │   │   ├── tickets/
│   │   │   ├── opd/
│   │   │   └── policy_vector_store/
│   │   └── main.py
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api.ts
│   │   └── styles.css
│   └── package.json
│
└── README.md
```

This structure highlights the main components involved in the multi-model chatbot. Additional project files and modules are omitted for readability.

## 3. Multi-Model Integration

The application supports two LLM providers:

- **Cohere:** Command A+ for chat generation and intent classification.
- **Groq:** Qwen for chat generation and intent classification.

Users select their preferred provider using the frontend model selector.

The backend uses a shared LLM router to direct supported model requests to the selected provider.

### Request Flow

```text
Employee
   |
   v
React Frontend
   |
   v
Select Cohere or Groq
   |
   v
FastAPI Chat Endpoint
   |
   v
Intent Classification
   |
   v
Dedicated Workflow Handler
   |
   +---- HR Policy Q&A
   |
   +---- Leave Application
   |
   +---- Support Ticket
   |
   +---- OPD Claim
   |
   +---- Conversation History
   |
   v
Response Streamed to Frontend
```

The system uses rule-based routing for certain straightforward requests and ongoing workflows. This reduces unnecessary LLM calls.

For other requests, the selected model assists with intent classification and response generation.

### LLM Router

The integration is organized into three modules:

| File | Responsibility |
|---|---|
| `cohere_client.py` | Communicates with Cohere |
| `groq_client.py` | Communicates with Groq |
| `llm_router.py` | Routes model requests to the selected provider |

The model router changes the LLM provider without requiring separate implementations of every HR workflow.

## 4. Retrieval-Augmented Generation (RAG)

Both providers share the same RAG pipeline for HR policy question answering.

### Document Ingestion

```text
Admin uploads an HR policy PDF
             |
             v
Extract text using PyMuPDF
             |
             v
Split text into chunks
             |
             v
Generate Cohere Embed 5 Pro embeddings
             |
             v
Store embeddings in Qdrant
```

### Policy Question Answering

```text
Employee asks a policy question
             |
             v
Generate query embedding using Cohere
             |
             v
Search relevant documents in Qdrant
             |
             v
Retrieve policy excerpts
             |
             v
Send context to selected LLM
       /                \
      v                  v
   Cohere               Groq
      \                  /
       v                v
    Generate grounded answer
             |
             v
   Return answer with citations
```

**Important:** Groq is used for text generation, while Cohere Embed 5 Pro remains the common embedding model for both providers.

This means users can switch between Cohere and Groq without re-embedding policy documents.

## 5. Implemented Features

### Authentication and User Management

- JWT-based employee authentication.
- Employee login and account-status validation.
- Protected chat and document endpoints.
- Employee-specific conversation history.

### Multi-Model Chat

- Cohere and Groq provider selection.
- Provider-aware intent classification.
- LLM-generated responses.
- Streaming responses through Server-Sent Events (SSE).
- Conversation history and follow-up questions.
- Automatic chat-title generation.
- Chat rename, pin, and delete.

### HR Policy Q&A

- Upload HR policy PDFs.
- Extract and index policy content.
- Semantic retrieval using Qdrant.
- Generate contextual answers using Cohere or Groq.
- Include document filename and page references.
- Respond appropriately when supporting policy information is unavailable.

### Leave Applications

- Recognize leave application requests.
- Collect leave information conversationally.
- Maintain a draft across messages.
- Request employee confirmation.
- Create local pending leave records.

### Support Ticket Management

- Recognize support-ticket requests.
- Collect issue details.
- Maintain ticket drafts.
- Request employee confirmation.
- Create local support tickets.
- View existing local tickets.

### OPD Claims

- Accept PDF, JPG, and PNG receipts.
- Extract information from text-based PDFs.
- Use supported multimodal models to read JPG/PNG receipts.
- Collect claim amount, treatment date, and description.
- Ask for missing details.
- Request confirmation before submission.
- Create local pending OPD claims.

### Conversation Memory

- Store persistent chat history in PostgreSQL.
- Use Redis as an optional cache.
- Retrieve previous conversations.
- Answer questions about the current conversation history.

## 6. Backend Setup

### Prerequisites

Ensure the following are installed:

- Python with pip
- PostgreSQL
- Redis
- Qdrant
- Cohere API credentials
- Groq API credentials

Docker may be used to run the database services.

The standalone MVP should use isolated database and vector-store instances rather than connecting to the original HR Pilot environment.

### Step 1 — Navigate to Backend

```powershell
cd backend
```

### Step 2 — Create and Activate Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If the virtual environment already exists, activate it without creating another one.

### Step 3 — Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

### Step 4 — Configure Environment Variables

Copy the example configuration:

```powershell
Copy-Item .env.example .env
```

Configure the database services, JWT secret, and API credentials.

The LLM provider credentials include:

```env
COHERE_API_KEY=your_cohere_api_key
GROQ_API_KEY=your_groq_api_key
```

Use `.env.example` for the complete configuration and actual model-setting variable names.

**Security:** Never commit real API keys, passwords, or the `.env` file to GitHub.

### Step 5 — Initialize Database

```powershell
python -m scripts.init_db
python -m scripts.seed_employee --email admin@example.com --name "Test Admin" --role admin
```

Set the test employee password using the project's supported seed process.

### Step 6 — Start Backend Server

```powershell
python -m uvicorn src.main:app --reload --port 8001
```

Backend URL:

`http://127.0.0.1:8001`

Swagger API documentation:

`http://127.0.0.1:8001/docs`

## 7. Frontend Setup

Open a separate terminal from the project root.

### Step 1 — Navigate to Frontend

```powershell
cd frontend
```

### Step 2 — Install Dependencies

```powershell
npm install
```

### Step 3 — Start Development Server

```powershell
npm run dev
```

Open the local URL displayed by Vite.

Ensure the frontend API configuration points to the running FastAPI backend.

### Using the Model Selector

1. Log in using the test employee account.
2. Open the chat interface.
3. Select Cohere or Groq from the model selector.
4. Start a conversation and send a message.
5. The selected provider is passed to the backend for supported model operations.

The frontend is designed to keep a conversation associated with its selected provider. Backend-side persistent enforcement of that association is not yet implemented.

## 8. Chat API

### Endpoint

`POST /api/hr/chat/get_response`

**Authentication:** Bearer token

**Content type:** `multipart/form-data`

| Parameter | Description |
|---|---|
| `user_query` | Employee message |
| `session_id` | Optional existing conversation ID |
| `provider` | `cohere` or `groq` |
| `stream_events` | Enable SSE streaming |
| `chat_history` | Accepted for compatibility |
| `attachment` | Optional OPD PDF/JPG/PNG file |

The API uses stored conversation history rather than trusting a client-supplied history.

### Example: Cohere

```powershell
curl.exe -N -X POST http://127.0.0.1:8001/api/hr/chat/get_response `
  -H "Authorization: Bearer YOUR_JWT_TOKEN" `
  -F "user_query=What is the annual leave policy?" `
  -F "provider=cohere" `
  -F "stream_events=true"
```

### Example: Groq

```powershell
curl.exe -N -X POST http://127.0.0.1:8001/api/hr/chat/get_response `
  -H "Authorization: Bearer YOUR_JWT_TOKEN" `
  -F "user_query=What is the annual leave policy?" `
  -F "provider=groq" `
  -F "stream_events=true"
```

For policy questions, upload at least one supported policy PDF before testing retrieval.

### SSE Response Events

The backend supports:

- `status` — Request processing status.
- `chunk` — Generated response text.
- `done` — Completion, session ID, and source metadata.
- `error` — Request or model failure.

## 9. Data Storage

### PostgreSQL

Stores employee records, conversation history, chat metadata, and local workflow records.

### Redis

Provides optional session caching. PostgreSQL remains the durable source for chat messages.

### Qdrant

Stores policy document vectors in the `policy_collection` collection.

The prototype uses Cohere Embed 5 Pro embeddings with a 2048-dimensional vector configuration.

### File Storage

Uploaded policy PDFs and OPD attachments are kept in private local storage.

Uploaded files, secrets, and local runtime data should remain excluded from Git.

## 10. Differences from Original HR Pilot

The original HR Pilot Chat Module and standalone MVP have different internal architectures.

| Component | Original HR Pilot | Standalone MVP |
|---|---|---|
| LLM | OpenAI GPT models | Cohere / Groq |
| Intent classification | Structured intent and entity extraction | Intent classification with rule-based shortcuts |
| Policy embeddings | OpenAI embeddings | Cohere Embed 5 Pro |
| RAG vector store | Qdrant | Qdrant |
| Session persistence | Redis-first, later PostgreSQL | PostgreSQL-first, Redis cache |
| Leave workflow | Original HR ticket integration | Local pending leave request |
| Ticket workflow | HR ticket integration and notifications | Local support tickets |
| OPD | Eligibility, document verification, original HR workflow | Simplified extraction and pending claims |
| Salary and payroll | Original external integrations | Not connected |

The systems may provide similar conversational experiences for supported scenarios, but their business operations are not functionally identical.

## 11. Known Limitations

This is a development MVP, not a production-ready replacement.

- No complete integration with the original HR Pilot database or HR services.
- No live Odoo/payroll transactions.
- Salary slip retrieval, salary advances, and provident fund loan workflows are not connected.
- Local leave and ticket records do not automatically execute original HR approval workflows.
- OPD claims remain pending until handled outside the prototype.
- No full scanned-PDF OCR equivalent to the original GPT-4o page-processing workflow.
- Some supporting code paths still default to Cohere.
- Backend-side provider locking per conversation is not implemented.
- Production deployment requires additional security, migrations, rate limiting, concurrency safeguards, and operational monitoring.

## 12. Project Objective

The primary purpose of this project is to evaluate **multi-model LLM integration** within an HR chatbot environment.

The MVP demonstrates how Cohere and Groq can use a common application backend, RAG architecture, and selected HR workflows while allowing users to choose a generation provider.

Future evaluation can measure:

- LLM API calls per user request.
- Response quality and policy grounding.
- Response latency.
- Model-specific reliability.
- Workflow success and failure rates.
- Differences between Cohere and Groq across the same test prompts.

The original HR Pilot application remains separate and unchanged.
