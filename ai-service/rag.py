import hashlib
import io
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from schemas import DocumentSummary, DocumentsResponse, IngestResponse, SourceItem

DEFAULT_PERSIST_DIR = str(Path(__file__).resolve().parent / "chroma_db")
COLLECTION_NAME = "witty_docs"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
# Cosine distance in [0, 2]: 0 = identical, 1 = orthogonal. 0.65 => similarity >= 0.35.
DEFAULT_MAX_DISTANCE = 0.65
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


@dataclass
class RetrievedChunk:
    source: str
    page: int | None
    score: float
    content: str

    def to_source_item(self) -> SourceItem:
        clean = " ".join(self.content.split())
        snippet = clean[:220] + ("..." if len(clean) > 220 else "")
        return SourceItem(
            source=self.source,
            page=self.page,
            score=self.score,
            snippet=snippet,
        )


def parse_file_bytes(filename: str, data: bytes) -> list[Document]:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    docs: list[Document] = []
    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        for page_num, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                docs.append(
                    Document(
                        page_content=text,
                        metadata={"source": filename, "page": page_num},
                    )
                )
    else:
        text = data.decode("utf-8", errors="replace").strip()
        if text:
            docs.append(Document(page_content=text, metadata={"source": filename}))

    if not docs:
        raise ValueError(f"No readable text found in '{filename}'.")
    return docs


def extract_clean_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "aside"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text("\n").splitlines()]
    return "\n".join(line for line in lines if line)


async def fetch_url_documents(url: str) -> list[Document]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must start with http:// or https://")

    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        resp = await client.get(url, headers={"User-Agent": "WittyAI-RAG/0.1"})
        resp.raise_for_status()

    text = extract_clean_html_text(resp.text)
    if not text:
        raise ValueError(f"No readable text extracted from '{url}'.")

    return [Document(page_content=text, metadata={"source": url})]


class DocumentStore:
    def __init__(
        self,
        persist_directory: str = DEFAULT_PERSIST_DIR,
        embeddings=None,
        collection_name: str = COLLECTION_NAME,
    ):
        self._persist_directory = persist_directory
        self._embeddings = embeddings
        self._collection_name = collection_name
        self._store: Chroma | None = None
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

    def _get_embeddings(self):
        if self._embeddings is None:
            model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            self._embeddings = OpenAIEmbeddings(model=model)
        return self._embeddings

    def _get_store(self) -> Chroma:
        if self._store is None:
            self._store = Chroma(
                collection_name=self._collection_name,
                embedding_function=self._get_embeddings(),
                persist_directory=self._persist_directory,
                collection_metadata={"hnsw:space": "cosine"},
            )
        return self._store

    def ingest_documents(self, docs: list[Document], source_label: str) -> IngestResponse:
        chunks = self._splitter.split_documents(docs)
        if not chunks:
            raise ValueError(f"No chunks produced for '{source_label}'.")

        combined = "\n".join(d.page_content for d in docs)
        doc_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]

        chunk_ids: list[str] = []
        for idx, chunk in enumerate(chunks):
            chunk.metadata["source"] = source_label
            chunk.metadata["doc_hash"] = doc_hash
            chunk.metadata["chunk_index"] = idx
            chunk_ids.append(f"{doc_hash}:{idx}")

        store = self._get_store()
        # Idempotent re-ingestion: remove prior chunks for the same content hash first.
        existing = store._collection.get(where={"doc_hash": doc_hash})
        if existing and existing.get("ids"):
            store._collection.delete(ids=existing["ids"])

        store.add_documents(chunks, ids=chunk_ids)
        return IngestResponse(
            source=source_label,
            chunks_added=len(chunks),
            total_chunks=store._collection.count(),
        )

    def retrieve(
        self,
        query: str,
        k: int = 4,
        max_distance: float = DEFAULT_MAX_DISTANCE,
    ) -> list[RetrievedChunk]:
        store = self._get_store()
        total = store._collection.count()
        if total == 0:
            return []

        results = store.similarity_search_with_score(query, k=min(k, total))
        hits: list[RetrievedChunk] = []
        for doc, distance in results:
            dist = float(distance)
            if dist > max_distance:
                continue
            similarity = max(0.0, round(1.0 - dist, 3))
            page_val = doc.metadata.get("page")
            hits.append(
                RetrievedChunk(
                    source=str(doc.metadata.get("source", "unknown")),
                    page=int(page_val) if page_val is not None else None,
                    score=similarity,
                    content=doc.page_content,
                )
            )
        return hits

    def list_documents(self) -> DocumentsResponse:
        store = self._get_store()
        total = store._collection.count()
        if total == 0:
            return DocumentsResponse(documents=[], total_chunks=0)

        data = store._collection.get(include=["metadatas"])
        counts = Counter(
            str((meta or {}).get("source", "unknown"))
            for meta in (data.get("metadatas") or [])
        )
        summaries = [
            DocumentSummary(source=src, chunks=cnt)
            for src, cnt in sorted(counts.items())
        ]
        return DocumentsResponse(documents=summaries, total_chunks=total)

    def clear(self) -> int:
        store = self._get_store()
        data = store._collection.get()
        ids = data.get("ids") or []
        if ids:
            store._collection.delete(ids=ids)
        return len(ids)


_default_store = DocumentStore()


def get_document_store() -> DocumentStore:
    return _default_store
