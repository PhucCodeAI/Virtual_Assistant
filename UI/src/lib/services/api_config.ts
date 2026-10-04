// src/lib/services/api_config.ts
//
// Tập trung cấu hình API endpoint. KHÔNG đọc env ở component/state —
// mọi nơi import từ file này.
//
// Env: VITE_BACKEND_URL (bắt buộc khi deploy).
// Fallback: http://localhost:8000 (dev local — dev không cần set env).

const FALLBACK_BASE_URL = "http://localhost:8000";

const envBaseUrl = (import.meta.env as Record<string, string | undefined>)
  .VITE_BACKEND_URL;

export const API_BASE_URL = envBaseUrl ?? FALLBACK_BASE_URL;

// Routes contract v2 (verify 2026-10-04 10:53 — BE đã push).
// Ticket UI-002-REPLY-3 M1 đã resolved.
export const ORCHESTRATOR_RUN_URL = `${API_BASE_URL}/orchestrator/run`;
export const ORCHESTRATOR_SYNC_URL = `${API_BASE_URL}/orchestrator/run/sync`;

// Trace dashboard (UI-007).
export const TRACES_BASE_URL = `${API_BASE_URL}/traces`;