"""OPD extraction routing with mocked models and database sessions."""
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
import pytest
from src.hr_management_agent.opd import conversation as opd


@pytest.fixture
def workflow(monkeypatch):
    draft=SimpleNamespace(fields={'amount':'2500','treatment_date':'2026-10-01',
        'description':'Doctor consultation'}, state='confirming',
        stored_filename='old.png', original_filename='old.png', content_type='image/png')
    db=MagicMock()
    session=MagicMock()
    session.__enter__.return_value=db
    monkeypatch.setattr(opd,'SessionLocal',lambda: session)
    monkeypatch.setattr(opd,'active_draft',lambda *args: draft)
    text=Mock(return_value={'amount':'3000'})
    vision=Mock(return_value={'amount':'3500'})
    monkeypatch.setattr(opd,'_ai_extract',text)
    monkeypatch.setattr(opd,'_vision_extract',vision)
    return draft,db,text,vision


@pytest.mark.parametrize('message', ['Change the amount to 3000',
    'PKR 3000 on 2026-10-01 for doctor consultation'])
def test_complete_draft_and_explicit_wording_still_use_llm(workflow,message):
    draft,db,text,vision=workflow
    reply=opd.process_opd_message('s',1,message,provider='groq')
    text.assert_called_once()
    assert text.call_args.kwargs['provider']=='groq'
    vision.assert_not_called()
    assert draft.fields['amount']=='3000'
    assert 'Please confirm' in reply
    db.add.assert_not_called()


def test_new_image_is_read_even_with_complete_fields(workflow):
    draft,db,text,vision=workflow
    draft.stored_filename=None
    opd.process_opd_message('s',1,'Read this receipt',
        {'stored_filename':'new.png','original_filename':'new.png','content_type':'image/png'},
        provider='groq')
    vision.assert_called_once()
    assert vision.call_args.kwargs['provider']=='groq'
    text.assert_not_called()
    assert draft.fields['amount']=='3500'


@pytest.mark.parametrize('pdf_text',['Receipt total 3000',''])
def test_pdf_uses_text_model_without_vision(workflow,monkeypatch,pdf_text):
    draft,db,text,vision=workflow
    draft.stored_filename=None
    monkeypatch.setattr(opd,'_pdf_text',Mock(return_value=pdf_text))
    opd.process_opd_message('s',1,'Amount is 3000',
        {'stored_filename':'new.pdf','original_filename':'new.pdf','content_type':'application/pdf'})
    text.assert_called_once()
    assert text.call_args.args[1]==pdf_text
    vision.assert_not_called()


def test_failed_extraction_cannot_create_claim(workflow):
    draft,db,text,vision=workflow
    draft.fields={}
    text.return_value={}
    reply=opd.process_opd_message('s',1,'My doctor bill')
    assert 'Please provide' in reply
    assert draft.state=='collecting'
    db.add.assert_not_called()


def test_cancellation_does_not_extract(workflow):
    draft,db,text,vision=workflow
    draft.stored_filename=None
    reply=opd.process_opd_message('s',1,'cancel')
    assert 'cancelled' in reply
    assert draft.state=='cancelled'
    text.assert_not_called()
    vision.assert_not_called()
