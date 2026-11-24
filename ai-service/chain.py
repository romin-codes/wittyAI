import os
import time
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from rag import RetrievedChunk
from schemas import ChatMessage, ChatResponse, UsageInfo

SYSTEM_PROMPT = (
    "You are WittyAI, a helpful, concise, and clear AI assistant. "
    "Use the conversation history to stay consistent with earlier turns."
)

RAG_SYSTEM_PROMPT = (
    "You are WittyAI, a helpful, concise, and clear AI assistant. "
    "Answer the user's question using the retrieved document context below whenever relevant. "
    "Cite supporting sources inline like [1], [2] matching the numbered excerpts. "
    "If the retrieved context does not contain the answer, say so clearly instead of guessing.\n\n"
    "Retrieved Context:\n{context}"
)

# Cap history so long threads do not blow up token cost or context limits.
MAX_HISTORY_MESSAGES = 20

CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{message}"),
    ]
)

RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", RAG_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{message}"),
    ]
)


def to_langchain_messages(history: list[ChatMessage]) -> list[BaseMessage]:
    recent = history[-MAX_HISTORY_MESSAGES:]
    messages: list[BaseMessage] = []
    for item in recent:
        if item.role == "user":
            messages.append(HumanMessage(content=item.content))
        else:
            messages.append(AIMessage(content=item.content))
    return messages


def format_context(chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        loc = f"{chunk.source}, p.{chunk.page}" if chunk.page else chunk.source
        blocks.append(f"[{idx}] ({loc}):\n{chunk.content}")
    return "\n\n".join(blocks)


def get_llm() -> ChatOpenAI:
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return ChatOpenAI(model=model_name, timeout=30, max_retries=2)


async def generate_reply(
    message: str,
    history: list[ChatMessage],
    llm=None,
    thread_id: str | None = None,
    retrieved_chunks: list[RetrievedChunk] | None = None,
) -> ChatResponse:
    model = llm or get_llm()
    chunks = retrieved_chunks or []
    lc_history = to_langchain_messages(history)
    config = {"metadata": {"thread_id": thread_id, "rag": bool(chunks)}} if thread_id else None

    if chunks:
        # Stop before StrOutputParser so we keep AIMessage.usage_metadata (tokens).
        chain = RAG_PROMPT | model
        payload = {
            "context": format_context(chunks),
            "history": lc_history,
            "message": message,
        }
    else:
        chain = CHAT_PROMPT | model
        payload = {"history": lc_history, "message": message}

    start = time.perf_counter()
    ai_msg = await chain.ainvoke(payload, config=config)
    latency_ms = int((time.perf_counter() - start) * 1000)

    usage_meta = getattr(ai_msg, "usage_metadata", None) or {}
    model_name = (
        getattr(model, "model_name", None)
        or getattr(model, "model", None)
        or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )

    return ChatResponse(
        reply=str(ai_msg.content),
        usage=UsageInfo(
            model=model_name,
            input_tokens=int(usage_meta.get("input_tokens", 0)),
            output_tokens=int(usage_meta.get("output_tokens", 0)),
            total_tokens=int(usage_meta.get("total_tokens", 0)),
            latency_ms=latency_ms,
        ),
        sources=[chunk.to_source_item() for chunk in chunks],
    )
