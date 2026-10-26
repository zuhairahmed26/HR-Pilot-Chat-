import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from src.core.config import get_settings
from src.database.database_connection import get_db
from src.database.models import PolicyDocument
from src.hr_management_agent.auth.authenticate import require_admin
from src.hr_management_agent.policy_vector_store.utils import ingest_pdf,delete_document_vectors

router=APIRouter(prefix='/api/hr/policy_vector_store',tags=['Policies'])
BASE=Path(__file__).resolve().parents[3]/'storage'/'policies'

@router.post('/upload')
async def upload_policy(file: UploadFile = File(...), db: Session=Depends(get_db),
                        admin: dict=Depends(require_admin)):
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400,'Only PDF files supported in this version')
    s=get_settings(); data=await file.read(s.MAX_POLICY_UPLOAD_MB*1024*1024+1)
    if len(data)>s.MAX_POLICY_UPLOAD_MB*1024*1024: raise HTTPException(413,'PDF is too large')
    if not data.startswith(b'%PDF-'): raise HTTPException(400,'Invalid PDF content')
    BASE.mkdir(parents=True,exist_ok=True)
    path=BASE/(str(uuid.uuid4())+'.pdf')
    path.write_bytes(data)
    doc=PolicyDocument(filename=Path(file.filename).name[:255],storage_path=str(path),
                       uploaded_by=admin['current_user_id'])
    try:
        db.add(doc);db.flush()
        doc.chunks=ingest_pdf(path,doc.id,doc.filename)
        db.commit();db.refresh(doc)
        return {'document_id':doc.id,'filename':doc.filename,'chunks':doc.chunks}
    except ValueError as exc:
        db.rollback();path.unlink(missing_ok=True)
        raise HTTPException(422,str(exc))
    except Exception:
        db.rollback();path.unlink(missing_ok=True)
        if doc.id: delete_document_vectors(doc.id)
        raise

@router.get('/documents')
def list_documents(db: Session=Depends(get_db),admin:dict=Depends(require_admin)):
    return [{'id':p.id,'filename':p.filename,'chunks':p.chunks,'uploaded_at':p.uploaded_at}
            for p in db.query(PolicyDocument).order_by(PolicyDocument.id.desc()).all()]

@router.delete('/documents/{document_id}')
def delete_document(document_id:int,db:Session=Depends(get_db),admin:dict=Depends(require_admin)):
    doc=db.get(PolicyDocument,document_id)
    if not doc: raise HTTPException(404,'Document not found')
    delete_document_vectors(doc.id)
    Path(doc.storage_path).unlink(missing_ok=True)
    db.delete(doc);db.commit()
    return {'deleted':document_id}
