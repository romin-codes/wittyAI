import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile

# Load ai-service/.env first; fall back to Backend/.env in local dev so the
# existing OPENAI_API_KEY works without duplicating secrets.
_SERVICE_DIR = Path(__file__).resolve().parent
load_dotenv(_SERVICE_DIR / ".env", override=True)
load_dotenv(_SERVICE_DIR.parent / "Backend" / ".env")

from chain import generate_reply, get_llm
from rag import (
    DocumentStore,
    fetch_url_documents,
    get_document_store,
    parse_file_bytes,
)
from schemas import (
    ChatRequest,
    ChatResponse,
    DocumentsResponse,
    IngestResponse,
    IngestUrlRequest,
)

app = FastAPI(
    title="WittyAI Service",
    version="0.2.0",
    description="LangChain + OpenAI + Chroma RAG service for WittyAI",
)


def get_llm_provider():
    return get_llm


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    llm_factory=Depends(get_llm_provider),
    store: DocumentStore = Depends(get_document_store),
):
    try:
        chunks = store.retrieve(req.message) if req.use_rag else []
        llm = llm_factory()
        return await generate_reply(
            message=req.message,
            history=req.history,
            llm=llm,
            thread_id=req.thread_id,
            retrieved_chunks=chunks,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}") from exc


@app.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    store: DocumentStore = Depends(get_document_store),
):
    filename = file.filename or "upload.txt"
    data = await file.read()
    try:
        docs = parse_file_bytes(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return store.ingest_documents(docs, source_label=filename)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ingestion failed: {exc}") from exc


@app.post("/ingest/url", response_model=IngestResponse)
async def ingest_url(
    req: IngestUrlRequest,
    store: DocumentStore = Depends(get_document_store),
):
    try:
        docs = await fetch_url_documents(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {exc}") from exc

    try:
        return store.ingest_documents(docs, source_label=req.url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ingestion failed: {exc}") from exc


@app.get("/documents", response_model=DocumentsResponse)
def list_documents(store: DocumentStore = Depends(get_document_store)):
    return store.list_documents()


@app.delete("/documents")
def clear_documents(store: DocumentStore = Depends(get_document_store)):
    deleted = store.clear()
    return {"deleted_chunks": deleted}
