# Backend conservative refactor audit

Reviewed: 11 November 2026

## Scope

Inspected all 40 project Python files under src/, scripts/ and tests/, plus README.md, requirements.txt, start.bat, .gitignore and .env.example setting names. Traced callers in backend source/tests/scripts and searched the sibling Frontend and Evaluation source for removed helper references. Installed packages, caches, generated reports, sample documents and private uploaded data are not application source and were not deleted. Live .env values were not inspected or changed.

## Decisions

This was not a rewrite. Most apparent duplication participates in different observable behavior. response_for is still used by the API and tests, so its callable behavior remains. ORM registration imports and FastAPI authorization dependencies remain even when their names are otherwise unused. Field-extraction regex and confirmation rules remain.

## File-by-file review

| File | Decision |
|---|---|
| `scripts/__init__.py` | Retained package marker; no business logic. |
| `scripts/init_db.py` | Retained CLI entry point and model-registration imports; not executed during review. |
| `scripts/init_leave_tables.py` | Retained CLI entry point and model-registration imports; not executed during review. |
| `scripts/init_opd_tables.py` | Retained CLI entry point and model-registration imports; not executed during review. |
| `scripts/init_ticket_tables.py` | Retained CLI entry point and model-registration imports; not executed during review. |
| `scripts/seed_employee.py` | Retained CLI entry point and model-registration imports; not executed during review. |
| `src/__init__.py` | Retained package marker; no business logic. |
| `src/core/__init__.py` | Retained package marker; no business logic. |
| `src/core/cohere_client.py` | Refactored: shared message builder; preserves twelve-message window, filtering, prompts, settings and SDK call counts. |
| `src/core/config.py` | Retained settings, including currently unused APP_ENV/BACKEND_URL, because they are part of configuration compatibility. |
| `src/core/groq_client.py` | Reviewed imports, definitions and callers; retained active code without behavior changes. |
| `src/core/llm_router.py` | Reviewed imports, definitions and callers; retained active code without behavior changes. |
| `src/database/__init__.py` | Retained package marker; no business logic. |
| `src/database/database_connection.py` | Reviewed imports, definitions and callers; retained active code without behavior changes. |
| `src/database/models.py` | Reviewed imports, definitions and callers; retained active code without behavior changes. |
| `src/hr_management_agent/__init__.py` | Retained package marker; no business logic. |
| `src/hr_management_agent/auth/__init__.py` | Retained package marker; no business logic. |
| `src/hr_management_agent/auth/api.py` | Reviewed imports, definitions and callers; retained active code without behavior changes. |
| `src/hr_management_agent/auth/authenticate.py` | Reviewed imports, definitions and callers; retained active code without behavior changes. |
| `src/hr_management_agent/chat/__init__.py` | Retained package marker; no business logic. |
| `src/hr_management_agent/chat/api.py` | Removed unused get_session import. All route and helper bodies preserved, including response_for compatibility behavior. |
| `src/hr_management_agent/chat/intent_classifier.py` | Retained LLM-only classification, context, JSON validation and fail-closed handling. |
| `src/hr_management_agent/chat/redis_client.py` | Removed uncalled get_session reader. Cache writes, ownership payload, TTL and deletion retained. |
| `src/hr_management_agent/leave/__init__.py` | Retained package marker; no business logic. |
| `src/hr_management_agent/leave/service.py` | Retained all logic and pre-existing whitespace edit; no transaction, extraction or provider changes. |
| `src/hr_management_agent/opd/__init__.py` | Retained package marker; no business logic. |
| `src/hr_management_agent/opd/conversation.py` | Removed unused os and public_claim imports. All extraction, validation, attachment and transaction code retained. |
| `src/hr_management_agent/opd/service.py` | Retained: direct upload differs from chat staging in status codes, messages and cleanup; not interchangeable. |
| `src/hr_management_agent/policy_vector_store/__init__.py` | Retained package marker; no business logic. |
| `src/hr_management_agent/policy_vector_store/api.py` | Reviewed imports, definitions and callers; retained active code without behavior changes. |
| `src/hr_management_agent/policy_vector_store/utils.py` | Reviewed imports, definitions and callers; retained active code without behavior changes. |
| `src/hr_management_agent/tickets/__init__.py` | Retained package marker; no business logic. |
| `src/hr_management_agent/tickets/service.py` | Retained all draft, confirmation, duplicate and expiry handling. |
| `src/main.py` | Retained startup/lifespan, health checks, CORS and router registration. |
| `tests/test_conversation_routing.py` | Retained regression tests. |
| `tests/test_intent_classifier.py` | Retained regression tests. |
| `tests/test_leave_validation.py` | Retained regression tests. |
| `tests/test_opd_validation.py` | Retained regression tests. |
| `tests/test_source_response.py` | Retained regression tests. |
| `tests/test_streaming.py` | Added three cases checking exact SDK arguments and bounded history for both Cohere completion modes. |

## Verification

- Baseline: 40 tests passed.
- Compared generated OpenAPI before/after: identical.
- Compared PostgreSQL CREATE TABLE definitions before/after: identical.
- Compared ASTs of every function/class in chat/api.py, leave/service.py, opd/conversation.py and tickets/service.py: identical.
- All 40 Python files compile.
- Final: 43 tests passed; one Qdrant server-version connectivity warning. Command: `.venv/Scripts/python.exe -m pytest tests -q --basetemp tmp/refactor-final-20261111 --tb=short`.
- Model responses are mocked in tests; live-provider accuracy and full deployed workflows were not exercised.

## Deferred findings

- requirements.txt does not declare groq although the source imports it; dependency repair should be handled separately.
- README contains outdated feature statements; no runtime behavior was changed to match the documentation.
- Policy upload and direct/chat OPD upload have different validation and cleanup behavior; consolidating them requires broader characterization tests.
- Git status is unavailable in this execution environment (Git cannot access the parent repository path). A local pre-edit source snapshot was used to verify exactly which files changed. No commits, resets or pushes were performed.
