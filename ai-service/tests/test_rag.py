import math
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings

from main import app
from rag import (
    DocumentStore,
    extract_clean_html_text,
    get_document_store,
    parse_file_bytes,
)


class KeywordBagEmbeddings(Embeddings):
    """Deterministic unit-normalized embeddings for offline cosine-similarity tests."""

    VOCAB = ["refund", "policy", "shipping", "password", "reset", "login", "weather", "rain"]

    def _embed(self, text: str) -> list[float]:
        lower = text.lower()
        vec = [1.0 if word in lower else 0.0 for word in self.VOCAB]
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            # Orthogonal fallback axis for completely unrelated text
            return [0.0] * len(self.VOCAB) + [1.0]
        return [v / norm for v in vec] + [0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def test_extract_clean_html_strips_nav_and_scripts():
    html = """
    <html>
      <head><script>console.log("ignore")</script><style>body{}</style></head>
      <body>
        <nav>Home Pricing Login</nav>
        <main><h1>Refund Policy</h1><p>30-day refunds apply.</p></main>
        <footer>Copyright 2026</footer>
      </body>
    </html>
    """
    cleaned = extract_clean_html_text(html)
    assert "Refund Policy" in cleaned
    assert "30-day refunds apply." in cleaned
    assert "Home Pricing Login" not in cleaned
    assert "console.log" not in cleaned
    assert "Copyright 2026" not in cleaned


def test_parse_file_rejects_unsupported_extension():
    try:
        parse_file_bytes("malware.exe", b"abc")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Unsupported file type" in str(exc)


def test_idempotent_ingestion_and_cosine_filtering(tmp_path):
    store = DocumentStore(
        persist_directory=str(tmp_path / "chroma"),
        embeddings=KeywordBagEmbeddings(),
        collection_name="test_rag",
    )
    docs = parse_file_bytes(
        "help.txt",
        b"Our refund policy allows shipping returns within 30 days.",
    )

    first = store.ingest_documents(docs, source_label="help.txt")
    second = store.ingest_documents(docs, source_label="help.txt")
    assert first.chunks_added == 1
    assert second.total_chunks == 1  # zero duplicates on re-ingest

    # Relevant query retrieves the doc with high cosine similarity
    hits = store.retrieve("What is the refund policy?")
    assert len(hits) == 1
    assert hits[0].source == "help.txt"
    assert hits[0].score > 0.5

    # Unrelated chitchat is filtered out by max_distance
    unrelated = store.retrieve("What is my name?")
    assert unrelated == []

    # List & clear endpoints work cleanly
    listed = store.list_documents()
    assert listed.total_chunks == 1
    assert listed.documents[0].source == "help.txt"
    assert store.clear() == 1
    assert store.list_documents().total_chunks == 0


def test_ingest_and_documents_endpoints(tmp_path):
    store = DocumentStore(
        persist_directory=str(tmp_path / "chroma_api"),
        embeddings=KeywordBagEmbeddings(),
        collection_name="test_api_rag",
    )
    app.dependency_overrides[get_document_store] = lambda: store
    try:
        client = TestClient(app)

        res = client.post(
            "/ingest/file",
            files={"file": ("notes.txt", b"Reset your password from the login page.", "text/plain")},
        )
        assert res.status_code == 200
        assert res.json()["chunks_added"] == 1

        docs_res = client.get("/documents")
        assert docs_res.status_code == 200
        assert docs_res.json()["total_chunks"] == 1

        bad_res = client.post(
            "/ingest/file",
            files={"file": ("pic.png", b"123", "image/png")},
        )
        assert bad_res.status_code == 400

        del_res = client.delete("/documents")
        assert del_res.status_code == 200
        assert del_res.json()["deleted_chunks"] == 1
    finally:
        app.dependency_overrides.clear()
