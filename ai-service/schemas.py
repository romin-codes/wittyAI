from typing import Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    thread_id: str | None = None
    message: str = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    use_rag: bool = True


class SourceItem(BaseModel):
    source: str
    page: int | None = None
    score: float
    snippet: str


class UsageInfo(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int


class ChatResponse(BaseModel):
    reply: str
    usage: UsageInfo
    sources: list[SourceItem] = Field(default_factory=list)


class IngestUrlRequest(BaseModel):
    url: str = Field(..., min_length=8)


class IngestResponse(BaseModel):
    source: str
    chunks_added: int
    total_chunks: int


class DocumentSummary(BaseModel):
    source: str
    chunks: int


class DocumentsResponse(BaseModel):
    documents: list[DocumentSummary]
    total_chunks: int
