// Base URL for the backend API.
// In production set VITE_API_URL in your Vercel project settings to the
// deployed backend URL, e.g. https://your-backend.vercel.app
// Falls back to the local dev server when the env var is not set.
// Trailing slashes are stripped so callers can safely do `${API_BASE_URL}/api/...`
// without producing a double slash (which triggers a CORS-blocked redirect).
export const API_BASE_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8080"
).replace(/\/+$/, "");
