// Base URL for the backend API.
// In production set VITE_API_URL in your Vercel project settings to the
// deployed backend URL, e.g. https://your-backend.vercel.app
// Falls back to the local dev server when the env var is not set.
export const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8080";
