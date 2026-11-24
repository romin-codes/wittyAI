import "dotenv/config";

export const getAIServiceUrl = () => {
  const configured = process.env.AI_SERVICE_URL?.trim();
  if (configured) return configured.replace(/\/+$/, "");
  // Default to local FastAPI service in dev; on Vercel fall back unless configured.
  if (!process.env.VERCEL) return "http://localhost:8000";
  return null;
};

const requireBaseUrl = () => {
  const baseUrl = getAIServiceUrl();
  if (!baseUrl) {
    throw new Error("AI_SERVICE_URL is not configured.");
  }
  return baseUrl;
};

const parseOrThrow = async (response) => {
  const text = await response.text();
  if (!response.ok) {
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      if (parsed?.detail) detail = parsed.detail;
    } catch {
      // keep raw text
    }
    const err = new Error(detail || `AI service error (${response.status})`);
    err.status = response.status;
    throw err;
  }
  return text ? JSON.parse(text) : {};
};

const getAIServiceResponse = async ({ threadId, message, history = [] }) => {
  const baseUrl = getAIServiceUrl();
  if (!baseUrl) {
    return null;
  }

  const response = await fetch(`${baseUrl}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      thread_id: threadId,
      message,
      history,
    }),
  });

  return parseOrThrow(response);
};

export const listDocuments = async () => {
  const baseUrl = requireBaseUrl();
  const response = await fetch(`${baseUrl}/documents`);
  return parseOrThrow(response);
};

export const clearDocuments = async () => {
  const baseUrl = requireBaseUrl();
  const response = await fetch(`${baseUrl}/documents`, { method: "DELETE" });
  return parseOrThrow(response);
};

export const ingestUrl = async (url) => {
  const baseUrl = requireBaseUrl();
  const response = await fetch(`${baseUrl}/ingest/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  return parseOrThrow(response);
};

export const ingestFileStream = async (req) => {
  const baseUrl = requireBaseUrl();
  const contentType = req.headers["content-type"];
  if (!contentType || !contentType.includes("multipart/form-data")) {
    const err = new Error("Expected multipart/form-data file upload.");
    err.status = 400;
    throw err;
  }

  const chunks = [];
  for await (const chunk of req) {
    chunks.push(chunk);
  }
  const body = Buffer.concat(chunks);

  const response = await fetch(`${baseUrl}/ingest/file`, {
    method: "POST",
    headers: { "Content-Type": contentType },
    body,
  });
  return parseOrThrow(response);
};

export default getAIServiceResponse;
