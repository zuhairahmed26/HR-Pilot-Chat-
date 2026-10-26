"""Cohere-powered intent routing, independent of action execution.

An intent is NOT permission to perform an HR action. Handlers must enforce
employee authorization and actually commit transactions before reporting success.
"""
import json
import logging
import re
from typing import Literal

from pydantic import BaseModel
from src.core.cohere_client import client, extract_text
from src.core.config import get_settings

logger = logging.getLogger(__name__)

Intent = Literal[
    'greeting', 'hr_policy_qa', 'conversation_history', 'leave_balance_inquiry',
    'leave_apply', 'document_request', 'ticket_creation', 'ticket_status_update',
    'retrieve_salary_slip', 'advance_salary_request', 'loan_against_pf',
    'opd_claim_request'
]

class IntentResult(BaseModel):
    intent: Intent

INTENTS = tuple(Intent.__args__)
CLASSIFIER_SYSTEM = (
    'You are an intent classifier for an HR employee chatbot. Return ONLY a JSON object '
    'with exactly one field: "intent". Choose exactly one from: '
    + ', '.join(INTENTS) + '. '
    'conversation_history: asks about messages exchanged with the assistant, what the user said, '
    'or a summary of this chat. '
    'hr_policy_qa: asks about HR policies, rights, rules, leave policy, benefits or general HR guidance. '
    'leave_balance_inquiry: asks for the user\'s PERSONAL remaining/accrued leave balance, not policy entitlement. '
    'leave_apply: wants to SUBMIT or request leave, not merely learn the policy. '
    'document_request: asks to request an employment document or certificate. '
    'ticket_creation: asks to create a support/HR ticket. '
    'ticket_status_update: asks about or changes an existing ticket status. '
    'retrieve_salary_slip: requests a personal payslip. '
    'advance_salary_request: wants an advance against salary. '
    'loan_against_pf: wants a provident fund loan. '
    'opd_claim_request: wants to claim medical expenses. '
    'greeting: only a greeting without another request. '
    'Use recent conversation turns to resolve elliptical follow-ups. '
    'A request about policy does not authorize any HR transaction. Generate JSON now.'
)


def _history_question(query: str) -> bool:
    q = re.sub(r'\s+', ' ', query.casefold()).strip()
    return any(phrase in q for phrase in (
        'first question', 'first message', 'previous question', 'last question',
        'earlier question', 'previous message', 'conversation history',
        'chat history', 'in this conversation', 'in our conversation',
        'in this chat', 'in our chat', 'what did i ask', 'what did i say',
        'what have i asked', 'summarize our conversation',
        'summarise our conversation', 'recap our conversation',
        'repeat my question', 'what were we discussing',
    ))


def _explicit_leave_application(query: str) -> bool:
    """Match clear employee leave requests without relying on network access.

    A policy question such as 'What is annual leave?' must not match.
    """
    q = re.sub(r'\s+', ' ', query.casefold()).strip()
    leave_word = bool(re.search(r'\b(annual leave|casual leave|medical leave|vacation|time off|days off|day off|leave)\b', q))
    request_phrase = bool(re.search(
        r'\b(i (?:want|need|would like|\x27d like|am planning)\b|'
        r'apply for|request (?:some |a )?leave|book (?:some )?leave|'
        r'take (?:\d+ |a few |some )?(?:days? )?off|submit (?:a |my )?leave)', q
    ))
    policy_question = bool(re.search(r'\b(policy|entitlement|allowed|eligible|how many days|what is)\b', q))
    return leave_word and request_phrase and not policy_question


def _explicit_ticket_creation(query: str) -> bool:
    """Recognize clear requests to open a support/HR ticket offline.

    Do not interpret questions about how tickets work as submission requests.
    """
    q = re.sub(r'\s+', ' ', query.casefold()).strip()
    ticket = bool(re.search(r'\b(?:support|helpdesk|hr|it)?\s*ticket\b', q))
    action = bool(re.search(
        r'\b(?:create|open|raise|submit|file|log|make)\s+(?:me\s+|a\s+|an\s+|new\s+|a\s+new\s+|my\s+)*'
        r'(?:(?:support|helpdesk|hr|it)\s+)?ticket\b', q
    ))
    request = bool(re.search(r'\b(?:please|can you|could you|i want to|i need to|i would like to|i\x27d like to)\b', q))
    # A direct imperative is sufficient; merely mentioning the word ticket is not.
    return ticket and action and not bool(re.search(r'\b(?:how (?:do|can|to)|what is|where|policy|procedure)\b', q))


def fallback_classify(query: str) -> str:
    """Conservative fallback; no new sensitive action is executed from it."""
    q = query.casefold().strip()
    if _history_question(q):
        return 'conversation_history'
    if _explicit_leave_application(query):
        return 'leave_apply'
    if _explicit_ticket_creation(query):
        return 'ticket_creation'
    if q in ('hi', 'hello', 'hey', 'good morning', 'good evening'):
        return 'greeting'
    patterns = (
        ('retrieve_salary_slip', ('salary slip', 'payslip', 'pay slip')),
        ('advance_salary_request', ('advance salary', 'salary advance')),
        ('loan_against_pf', ('provident fund loan', 'pf loan', 'loan against pf')),
        ('opd_claim_request', ('opd claim', 'medical reimbursement')),
        ('leave_apply', ('apply for leave', 'request leave', 'leave application')),
        ('leave_balance_inquiry', ('leave balance', 'remaining leave', 'leaves left')),
        ('ticket_status_update', ('ticket status', 'update ticket')),
        ('ticket_creation', ('create ticket', 'raise a ticket', 'open a ticket')),
        ('document_request', ('request document', 'employment letter', 'experience letter')),
    )
    for intent, phrases in patterns:
        if any(phrase in q for phrase in phrases):
            return intent
    return 'hr_policy_qa'


def classify_intent(query: str, history: list[dict] | None = None) -> str:
    """Return a validated intent. Never trust an unvalidated model label."""
    if _history_question(query):
        return 'conversation_history'  # guaranteed precision for history requests
    if _explicit_leave_application(query):
        return 'leave_apply'  # explicit action phrasing needs no API call
    if _explicit_ticket_creation(query):
        return 'ticket_creation'  # explicit action phrasing needs no API call
    snippets = []
    for msg in (history or [])[-6:]:
        if msg.get('role') in ('user', 'assistant') and isinstance(msg.get('content'), str):
            snippets.append({'role': msg['role'], 'content': msg['content'][:600]})
    prompt = json.dumps({'history': snippets, 'latest_user_message': query}, ensure_ascii=False)
    try:
        response = client().chat(
            model=get_settings().COHERE_CHAT_MODEL,
            messages=[
                {'role': 'system', 'content': CLASSIFIER_SYSTEM},
                {'role': 'user', 'content': 'Classify this HR request. Output a JSON object: ' + prompt},
            ],
            response_format={'type': 'json_object'},
            temperature=0,
        )
        return IntentResult.model_validate(json.loads(extract_text(response))).intent
    except Exception:
        logger.warning('Cohere intent classification failed; using safe fallback', exc_info=True)
        return fallback_classify(query)
