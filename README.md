# HR Pilot Chat — AI-Powered HR Assistant

An AI-powered HR management assistant built using **Cohere, FastAPI, React, PostgreSQL, Redis, and Qdrant**.

This project provides a conversational interface for HR-related inquiries and employee self-service workflows. Employees can ask questions about company policies, check leave balances, submit leave applications, create support tickets, and submit OPD reimbursement claims using natural language.

## Features

### AI-Powered HR Chat
- Conversational AI powered by Cohere Command A+
- Real-time response streaming
- Multi-turn conversation history
- AI-powered intent classification
- Session management

### Document Intelligence and RAG
- PDF document ingestion
- Semantic search using Cohere Embed 5 Pro
- Vector storage and retrieval using Qdrant
- Source-grounded policy answers with document citations

### Employee Self-Service
- Leave balance inquiries
- Leave application submission with confirmation
- Support ticket creation and tracking
- OPD reimbursement claims through natural-language conversation
- PDF and image receipt uploads
- Follow-up questions for missing claim details
- Claim history and status tracking

### Security and Authentication
- JWT-based authentication
- Protected API endpoints
- Employee-specific records
- Private storage for uploaded claim attachments

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend | Python, FastAPI |
| Generative AI | Cohere Command A+ |
| Embeddings | Cohere Embed 5 Pro |
| Relational Database | PostgreSQL |
| Vector Database | Qdrant |
| Caching and Sessions | Redis |
| Authentication | JWT |
| Document Processing | PyMuPDF |

## System Architecture

```text
Employee
   |
   v
React Frontend
   |
   v
FastAPI Backend
   |
   +-- Authentication
   |
   +-- HR Chat Agent
   |      |
   |      +-- Cohere Command A+
   |      +-- Intent Classification
   |      +-- Conversation History
   |
   +-- Policy RAG
   |      |
   |      +-- Cohere Embed 5 Pro
   |      +-- Qdrant Vector Database
   |
   +-- HR Workflows
   |      |
   |      +-- Leave Requests
   |      +-- Support Tickets
   |      +-- OPD Claims
   |
   +-- PostgreSQL
   +-- Redis
   +-- Private Attachment Storage
```

## Project Structure

```text
HR-Pilot-Chat-/
├── backend/
│   ├── src/
│   ├── scripts/
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── .env.example
│
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.12
- Node.js and npm
- PostgreSQL
- Redis
- Qdrant
- Cohere API key

### Backend Setup

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment and install dependencies:

```bash
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

Create a `.env` file using `backend/.env.example` and configure your database, Redis, Qdrant, JWT settings, and Cohere API key.

Initialize the database using the scripts in `backend/scripts/`, then start FastAPI:

```bash
python -m uvicorn src.main:app --reload --port 8001
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` in your browser.

## OPD Claim Workflow

1. Open the AI Assistant.
2. Request an OPD claim using natural language.
3. Attach a PDF, PNG, or JPG receipt.
4. The assistant extracts available claim information.
5. The assistant asks follow-up questions for missing details.
6. Review and confirm the claim.
7. The claim is stored in PostgreSQL with a pending status.
8. Track the claim in the OPD Claims history page.

## Current Scope

This repository is a standalone HR assistant MVP.

- HR requests are stored locally in PostgreSQL.
- Leave requests and OPD claims are not automatically approved.
- No payroll transfers or reimbursements are performed.
- External Odoo synchronization is not included.
- AI-extracted receipt details must be reviewed before submission.

## License

No open-source license has been assigned to this repository.