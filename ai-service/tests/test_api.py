from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from chain import MAX_HISTORY_MESSAGES
from main import app, get_llm_provider
from rag import RetrievedChunk, get_document_store


class EmptyStore:
    def retrieve(self, query: str, k: int = 4):
        return []


class FakeHitStore:
    def retrieve(self, query: str, k: int = 4):
        return [
            RetrievedChunk(
                source="policy.pdf",
                page=2,
                score=0.88,
                content="International orders can be refunded within 30 days.",
            )
        ]


def make_fake_llm(captured: list):
    def _respond(prompt_value):
        messages = prompt_value.to_messages()
        captured.append(messages)
        return AIMessage(
            content=f"echo: {messages[-1].content}",
            usage_metadata={
                "input_tokens": 25,
                "output_tokens": 10,
                "total_tokens": 35,
            },
        )

    return RunnableLambda(_respond)


def test_health():
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "model" in body


def test_chat_returns_reply_and_usage():
    captured = []
    app.dependency_overrides[get_llm_provider] = lambda: (lambda: make_fake_llm(captured))
    app.dependency_overrides[get_document_store] = lambda: EmptyStore()
    try:
        client = TestClient(app)
        res = client.post(
            "/chat",
            json={
                "thread_id": "t-1",
                "message": "What is my name?",
                "history": [
                    {"role": "user", "content": "My name is Romin."},
                    {"role": "assistant", "content": "Nice to meet you, Romin!"},
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()
    assert body["reply"] == "echo: What is my name?"
    assert body["sources"] == []
    assert body["usage"]["input_tokens"] == 25
    assert body["usage"]["output_tokens"] == 10
    assert body["usage"]["total_tokens"] == 35
    assert body["usage"]["latency_ms"] >= 0

    sent = captured[0]
    assert len(sent) == 4
    assert sent[0].type == "system"
    assert sent[1].type == "human" and "Romin" in sent[1].content
    assert sent[2].type == "ai"
    assert sent[3].type == "human" and sent[3].content == "What is my name?"


def test_chat_includes_rag_context_and_sources_when_docs_match():
    captured = []
    app.dependency_overrides[get_llm_provider] = lambda: (lambda: make_fake_llm(captured))
    app.dependency_overrides[get_document_store] = lambda: FakeHitStore()
    try:
        client = TestClient(app)
        res = client.post(
            "/chat",
            json={"thread_id": "t-rag", "message": "What is the refund window?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()
    assert len(body["sources"]) == 1
    assert body["sources"][0]["source"] == "policy.pdf"
    assert body["sources"][0]["page"] == 2
    assert body["sources"][0]["score"] == 0.88

    # System prompt must include the retrieved context block
    system_prompt = captured[0][0].content
    assert "Retrieved Context" in system_prompt
    assert "policy.pdf, p.2" in system_prompt
    assert "refunded within 30 days" in system_prompt


def test_chat_caps_long_history():
    captured = []
    app.dependency_overrides[get_llm_provider] = lambda: (lambda: make_fake_llm(captured))
    app.dependency_overrides[get_document_store] = lambda: EmptyStore()
    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg-{i}"}
        for i in range(MAX_HISTORY_MESSAGES + 10)
    ]
    try:
        client = TestClient(app)
        res = client.post(
            "/chat",
            json={"message": "latest", "history": long_history},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    sent = captured[0]
    assert len(sent) == MAX_HISTORY_MESSAGES + 2
    assert sent[1].content == "msg-10"


def test_chat_rejects_empty_message():
    client = TestClient(app)
    res = client.post("/chat", json={"message": ""})
    assert res.status_code == 422


def test_chat_handles_provider_failure_gracefully():
    def _boom():
        raise RuntimeError("simulated timeout")

    app.dependency_overrides[get_llm_provider] = lambda: _boom
    app.dependency_overrides[get_document_store] = lambda: EmptyStore()
    try:
        client = TestClient(app)
        res = client.post("/chat", json={"message": "hello"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 502
    assert "simulated timeout" in res.json()["detail"]
