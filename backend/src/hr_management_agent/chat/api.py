import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse, FileResponse
import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.database.database_connection import get_db,SessionLocal
from src.database.models import HRChatHistory
from src.hr_management_agent.auth.authenticate import get_current_employee
from src.hr_management_agent.chat.redis_client import get_session,set_session,delete_session
from src.hr_management_agent.policy_vector_store.utils import search_policy
from src.core.cohere_client import complete, stream_complete
from src.hr_management_agent.chat.intent_classifier import classify_intent
from src.hr_management_agent.leave.service import (has_active_draft, process_leave_message, list_leave_requests)
from src.hr_management_agent.tickets.service import (has_active_ticket_draft, process_ticket_message, list_tickets)
from src.hr_management_agent.opd.service import (create_claim, list_claims, get_claim, STORAGE_DIR)
from src.hr_management_agent.opd.conversation import (has_active_opd_draft, is_opd_request, stage_attachment, process_opd_message)

log=logging.getLogger(__name__)
router=APIRouter(prefix='/api/hr/chat',tags=['Chat'])
EXTERNAL_ACTIONS=('document_request','retrieve_salary_slip',
                  'advance_salary_request','loan_against_pf','ticket_status_update')

class RenameChat(BaseModel):
    chat_title: str | None = None
    pinned: bool | None = None


def owned(db: Session,session_id: str,employee_id: int) -> HRChatHistory:
    row=db.query(HRChatHistory).filter_by(session_id=session_id,employee_id=employee_id).first()
    if not row: raise HTTPException(404,'Chat session not found')
    return row

CONVERSATION_SYSTEM = (
    'You are the HR Pilot assistant. The prior user and assistant messages in this '
    'chat are included before the latest user message. For questions about the '
    'conversation, use those messages rather than HR policy documents. '
    'Quote earlier user messages exactly when requested. '
    'If the requested information is not in this conversation, say so clearly. '
    'Never invent prior messages or claim an HR operation was completed.'
)


def response_for(query:str,history:list[dict],user:dict, intent: str | None = None) -> tuple[str,list[dict]]:
    intent = intent or classify_intent(query, history)
    if intent=='leave_balance_inquiry':
        balances=user.get('current_user_leave_balance') or {}
        answer=('Your recorded leave balances are: '+json.dumps(balances) if balances
                else 'No leave balance is recorded for your account in this prototype.')
        return answer,[]
    if intent in EXTERNAL_ACTIONS:
        return (f'The {intent.replace("_"," ")} workflow is not connected in this standalone prototype. '
                'No request or payroll transaction has been submitted.'),[]
    if intent=='greeting':
        return 'Hello! I can answer questions from uploaded HR policies and show your recorded leave balance.',[]
    if intent == 'conversation_history':
        if not history:
            return 'There are no previous messages in this conversation yet.', []
        return complete(CONVERSATION_SYSTEM, query, history), []
    refs=search_policy(query)
    if not refs:
        return ('I cannot verify that from an HR policy yet. Ask an administrator to upload policy PDFs before asking policy questions.'),[]
    context='\n\n'.join(f'[Source {i}] {r["filename"]}, page {r["page"]}: {r["text"]}' for i,r in enumerate(refs,1))
    system=('You are the HR Pilot policy assistant. Answer ONLY from the provided policy excerpts. '
            'If evidence does not establish the answer, explicitly say so. Cite filename and page in the answer. '
            'Do not claim an HR action was submitted or an employee balance exists unless supplied.')
    answer=complete(system, f'POLICY EXCERPTS:\n{context}\n\nQUESTION: {query}',history)
    return answer,refs

def public_policy_sources(refs: list[dict], max_sources: int = 5) -> list[dict]:
    """Expose citation metadata only; never ship full retrieved policy chunks.

    Full source text remains available to the LLM inside response_for().
    """
    result = []
    seen = set()
    for ref in refs:
        filename = ref.get('filename')
        page = ref.get('page')
        if not filename or page is None:
            continue
        key = (filename, page)
        if key in seen:
            continue
        seen.add(key)
        source = {'filename': filename, 'page': page}
        if isinstance(ref.get('score'), (int, float)):
            source['score'] = round(float(ref['score']), 4)
        result.append(source)
        if len(result) >= max_sources:
            break
    return result

def generate_title(query: str) -> str:
    return (query.strip().replace('\n',' ')[:50] or 'New Chat')

def stream_and_save(session_id: str, query: str, employee_id: int, user: dict, result: dict, staged_attachment: dict | None = None):
    """Yield real text fragments, then persist complete history after successful generation.

    The caller emits the done event only after this function returns successfully.
    """
    with SessionLocal() as db:
        row = db.query(HRChatHistory).filter_by(
            session_id=session_id, employee_id=employee_id
        ).first()
        history = list(row.chat_data or []) if row else []

    if staged_attachment or has_active_opd_draft(session_id, employee_id) or is_opd_request(query):
        intent = 'opd_claim_request'
    elif has_active_draft(session_id, employee_id):
        intent = 'leave_apply'
    elif has_active_ticket_draft(session_id, employee_id):
        intent = 'ticket_creation'
    else:
        intent = classify_intent(query, history)
    refs = []
    if intent == 'opd_claim_request':
        fragments = iter([process_opd_message(session_id, employee_id, query, staged_attachment)])
    elif intent == 'leave_apply':
        fragments = iter([process_leave_message(session_id, employee_id, query, history)])
    elif intent == 'ticket_creation':
        fragments = iter([process_ticket_message(session_id, employee_id, query)])
    elif intent == 'ticket_status_update':
        tickets = list_tickets(employee_id)
        fragments = iter([('Your local tickets: ' + json.dumps(tickets[:10])) if tickets else 'No local support tickets found.'])
    elif intent == 'conversation_history':
        # For conversation questions use the authenticated session history.
        # Do not search Qdrant: policy excerpts cannot reveal prior user messages.
        if history:
            fragments = stream_complete(CONVERSATION_SYSTEM, query, history)
        else:
            fragments = iter(['There are no previous messages in this conversation yet.'])
    elif intent == 'hr_policy_qa':
        refs = search_policy(query)
        if refs:
            context = '\n\n'.join(
                f'[Source {i}] {ref["filename"]}, page {ref["page"]}: {ref["text"]}'
                for i, ref in enumerate(refs, 1)
            )
            system = (
                'You are the HR Pilot policy assistant. Answer ONLY from the provided policy excerpts. '
                'If evidence does not establish the answer, explicitly say so. '
                'Cite filename and page in the answer. '
                'Do not claim an HR action was submitted or an employee balance exists unless supplied.'
            )
            prompt = f'POLICY EXCERPTS:\n{context}\n\nQUESTION: {query}'
            fragments = stream_complete(system, prompt, history)
        else:
            fragments = iter([
                'I cannot verify that from an HR policy yet. '
                'Ask an administrator to upload policy PDFs before asking policy questions.'
            ])
    else:
        # Deterministic routes retain their original messages and need no model call.
        answer, _ = response_for(query, history, user, intent=intent)
        fragments = iter([answer])

    parts = []
    for fragment in fragments:
        parts.append(fragment)
        yield fragment

    answer = ''.join(parts).strip()
    if not answer:
        raise RuntimeError('Cohere returned an empty response; chat was not saved')

    displayed_query = query + (f'\n[Attached OPD slip: {staged_attachment["original_filename"]}]' if staged_attachment else '')
    history.extend([{'role': 'user', 'content': displayed_query},
                    {'role': 'assistant', 'content': answer}])
    with SessionLocal() as db:
        row = db.query(HRChatHistory).filter_by(
            session_id=session_id, employee_id=employee_id
        ).first()
        if row is None:
            row = HRChatHistory(
                session_id=session_id, employee_id=employee_id,
                chat_title=generate_title(query), chat_data=history
            )
            db.add(row)
        else:
            row.chat_data = history
        db.commit()
    try:
        set_session(session_id, employee_id, history)
    except Exception:
        log.warning('Redis cache unavailable; history remains in PostgreSQL', exc_info=True)
    result['sources'] = public_policy_sources(refs)

@router.post('/get_response')
async def get_response(user_query: Annotated[str,Form()], session_id: Annotated[str|None,Form()]=None,
    chat_history: Annotated[str,Form()]='[]',stream_events: Annotated[bool,Form()]=False,
    attachment: UploadFile | None = File(default=None),
    current_user:dict=Depends(get_current_employee)):
    if not user_query.strip() and attachment is None: raise HTTPException(422,'user_query cannot be empty')
    if len(user_query)>20000: raise HTTPException(413,'Message too long')
    session_id=session_id or str(uuid.uuid4())
    user_id=current_user['current_user_id']
    # Ownership must be checked before beginning the generator, including on reused session IDs.
    with SessionLocal() as db:
        existing=db.query(HRChatHistory).filter_by(session_id=session_id).first()
        if existing and existing.employee_id != user_id: raise HTTPException(403,'Not your chat session')
    staged = await stage_attachment(attachment) if attachment else None
    message = user_query.strip() or 'I would like to submit an OPD claim.'
    def generate():
        try:
            if stream_events: yield 'event: status\ndata: '+json.dumps({'loading':'Generating response'})+'\n\n'
            else: yield json.dumps({'loading':'Generating response'})+'\n'
            result = {}
            for fragment in stream_and_save(session_id, message, user_id, current_user, result, staged):
                if stream_events:
                    yield 'event: chunk\ndata: '+json.dumps({'text': fragment})+'\n\n'
                else:
                    yield fragment
            if stream_events:
                yield 'event: done\ndata: '+json.dumps({
                    'session_id': session_id, 'sources': result['sources']
                })+'\n\n' 
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            log.warning('Cohere connection failed during chat processing')
            error_message = 'AI provider temporarily unavailable. Check your saved requests before retrying an action.'
            if stream_events:
                yield 'event: error\ndata: '+json.dumps({'error': error_message, 'code':'AI_PROVIDER_UNAVAILABLE'})+'\n\n'
            else: yield '\n'+error_message
        except Exception:
            log.exception('Chat generation failed')
            if stream_events:
                yield 'event: error\ndata: '+json.dumps({'error':'Chat generation failed'})+'\n\n'
            else: yield '\nUnable to generate a response. Please try again.'
    return StreamingResponse(generate(),media_type='text/event-stream' if stream_events else 'text/plain',
        headers={'X-Chat-Session-ID':session_id,'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@router.get('/leave_requests')
def get_leave_requests(user:dict=Depends(get_current_employee)):
    return list_leave_requests(user['current_user_id'])

@router.get('/tickets')
def get_local_tickets(user:dict=Depends(get_current_employee)):
    return list_tickets(user['current_user_id'])

@router.post('/opd_claims', status_code=201)
async def submit_opd_claim(
    amount: Annotated[str, Form()],
    treatment_date: Annotated[str, Form()],
    description: Annotated[str, Form()],
    attachment: Annotated[UploadFile, File()],
    user: dict = Depends(get_current_employee),
):
    """Authenticated multipart upload: PDF/JPEG/PNG, max 10 MB; status is pending."""
    return await create_claim(user['current_user_id'], amount, treatment_date, description, attachment)


@router.get('/opd_claims')
def get_opd_claims(user: dict = Depends(get_current_employee)):
    return list_claims(user['current_user_id'])


@router.get('/opd_claims/{claim_id}/attachment')
def download_opd_attachment(claim_id: int, user: dict = Depends(get_current_employee)):
    claim = get_claim(user['current_user_id'], claim_id)
    path = STORAGE_DIR / claim.stored_filename
    if not path.is_file():
        raise HTTPException(404, 'Attachment file not found')
    return FileResponse(path, media_type=claim.content_type,
                        filename=claim.original_filename, content_disposition_type='attachment')


@router.get('/all')
def all_chats(user:dict=Depends(get_current_employee),db:Session=Depends(get_db)):
    chats=db.query(HRChatHistory).filter_by(employee_id=user['current_user_id']).order_by(HRChatHistory.created_at.desc()).all()
    return [{'session_id':c.session_id,'chat_title':c.chat_title,'created_at':c.created_at,
             'pinned_at':c.pinned_at} for c in chats]

@router.get('/{session_id}')
def get_chat(session_id:str,user:dict=Depends(get_current_employee),db:Session=Depends(get_db)):
    c=owned(db,session_id,user['current_user_id'])
    return {'session_id':c.session_id,'chat_title':c.chat_title,'chat_data':c.chat_data,
            'created_at':c.created_at,'pinned_at':c.pinned_at}

@router.patch('/{session_id}')
def update_chat(session_id:str,payload:RenameChat,user:dict=Depends(get_current_employee),db:Session=Depends(get_db)):
    c=owned(db,session_id,user['current_user_id'])
    if payload.chat_title is not None:
        if not payload.chat_title.strip(): raise HTTPException(422,'Title cannot be empty')
        c.chat_title=payload.chat_title.strip()[:100]
    if payload.pinned is not None: c.pinned_at=datetime.now(timezone.utc) if payload.pinned else None
    db.commit()
    return {'session_id':c.session_id,'chat_title':c.chat_title,'pinned_at':c.pinned_at}

@router.delete('/{session_id}')
def remove_chat(session_id:str,user:dict=Depends(get_current_employee),db:Session=Depends(get_db)):
    c=owned(db,session_id,user['current_user_id']);db.delete(c);db.commit()
    try: delete_session(session_id)
    except Exception: log.warning('Redis unavailable',exc_info=True)
    return {'deleted':session_id}

@router.post('/expire_session')
def expire_session(session_id:Annotated[str,Form()],user:dict=Depends(get_current_employee),db:Session=Depends(get_db)):
    owned(db,session_id,user['current_user_id'])
    try: delete_session(session_id)
    except Exception: pass
    return {'status':'expired','session_id':session_id}

@router.post('/expire_user_sessions_from_redis')
def expire_user_sessions(user:dict=Depends(get_current_employee),db:Session=Depends(get_db)):
    ids=[row.session_id for row in db.query(HRChatHistory.session_id).filter_by(employee_id=user['current_user_id'])]
    count=0
    for sid in ids:
        try: delete_session(sid);count+=1
        except Exception: break
    return {'expired':count}
