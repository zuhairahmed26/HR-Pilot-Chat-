import uuid
from pathlib import Path
import fitz
from qdrant_client import QdrantClient, models
from src.core.config import get_settings
from src.core.cohere_client import client

settings = get_settings()
qdrant = QdrantClient(host=settings.VECTOR_DB_HOST,port=settings.VECTOR_DB_PORT,timeout=20)

def ensure_collection():
    if not qdrant.collection_exists(settings.VECTOR_COLLECTION_NAME):
        qdrant.create_collection(settings.VECTOR_COLLECTION_NAME,
            vectors_config=models.VectorParams(size=settings.VECTOR_DIMENSION,distance=models.Distance.COSINE))
    else:
        info = qdrant.get_collection(settings.VECTOR_COLLECTION_NAME)
        configured = info.config.params.vectors
        size = getattr(configured,'size',None)
        if size is not None and size != settings.VECTOR_DIMENSION:
            raise ValueError(f'Existing collection dimension {size} differs from {settings.VECTOR_DIMENSION}')

def embed(texts: list[str], input_type: str):
    results=[]
    for start in range(0,len(texts),32):
        response = client().embed(texts=texts[start:start+32],model=settings.COHERE_EMBED_MODEL,
                                  input_type=input_type,output_dimension=settings.VECTOR_DIMENSION,
                                  embedding_types=['float'])
        results.extend(response.embeddings.float)
    if any(len(vec) != settings.VECTOR_DIMENSION for vec in results):
        raise ValueError('Unexpected Cohere embedding dimension')
    return results

def chunks_from_pdf(path: Path) -> list[tuple[int,str]]:
    chunks=[]
    with fitz.open(path) as doc:
        for n,page in enumerate(doc,1):
            text=' '.join(page.get_text('text').split())
            for i in range(0,len(text),1700):
                chunk=text[i:i+1900]
                if chunk.strip(): chunks.append((n,chunk))
    return chunks

def ingest_pdf(path: Path, document_id: int, filename: str) -> int:
    chunks=chunks_from_pdf(path)
    if not chunks: raise ValueError('PDF has no extractable text; scanned PDFs require OCR')
    ensure_collection()
    vectors=embed([c for _,c in chunks],'search_document')
    points=[models.PointStruct(id=str(uuid.uuid4()),vector=v,payload={
          'document_id':document_id,'filename':filename,'page':page,'text':text})
          for (page,text),v in zip(chunks,vectors)]
    for start in range(0,len(points),64):
        qdrant.upsert(collection_name=settings.VECTOR_COLLECTION_NAME,points=points[start:start+64],wait=True)
    return len(points)

def search_policy(query: str, limit: int = 5) -> list[dict]:
    if not qdrant.collection_exists(settings.VECTOR_COLLECTION_NAME): return []
    vector=embed([query],'search_query')[0]
    result=qdrant.query_points(collection_name=settings.VECTOR_COLLECTION_NAME,query=vector,
                               limit=limit,with_payload=True)
    return [{'text':p.payload['text'],'filename':p.payload['filename'],
             'page':p.payload['page'],'score':p.score} for p in result.points]

def delete_document_vectors(document_id: int):
    if qdrant.collection_exists(settings.VECTOR_COLLECTION_NAME):
        qdrant.delete(collection_name=settings.VECTOR_COLLECTION_NAME,points_selector=models.FilterSelector(
            filter=models.Filter(must=[models.FieldCondition(key='document_id',match=models.MatchValue(value=document_id))])))
