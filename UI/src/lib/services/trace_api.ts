// src/lib/services/trace_api.ts
//
// API client cho trace dashboard (UI-007).
//
// Q2 UI-007-REPLY-2: BE giữ raw array cho list. FE gọi song song
// listTraces + countTraces qua Promise.all để có đủ data cho pagination.
// Q4: /traces/session/{id} deprecated — dùng ?session_id= param.

import { TRACES_BASE_URL } from "./api_config";
import type {
  TraceSummary,
  TraceDetail,
  FinalStatus,
} from "$lib/state/types";

// ============================================================
// Public types
// ============================================================

export interface ListTracesParams {
  limit?: number;
  offset?: number;
  status?: FinalStatus | "";
  session_id?: string;
}

export interface CountTracesParams {
  status?: FinalStatus | "";
  session_id?: string;
}

export class TraceApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "TraceApiError";
  }
}

// ============================================================
// Public API
// ============================================================

export async function listTraces(
  params: ListTracesParams = {},
): Promise<TraceSummary[]> {
  const url = buildUrl(TRACES_BASE_URL, {
    limit: params.limit ?? 20,
    offset: params.offset ?? 0,
    status: params.status,
    session_id: params.session_id,
  });
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  await assertOk(response);
  return (await response.json()) as TraceSummary[];
}

export async function countTraces(
  params: CountTracesParams = {},
): Promise<number> {
  const url = buildUrl(`${TRACES_BASE_URL}/stats/count`, {
    status: params.status,
    session_id: params.session_id,
  });
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  await assertOk(response);
  const data = (await response.json()) as { count: number };
  return data.count;
}

export async function getTrace(traceId: string): Promise<TraceDetail> {
  const url = `${TRACES_BASE_URL}/${encodeURIComponent(traceId)}`;
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  await assertOk(response);
  return (await response.json()) as TraceDetail;
}

export async function deleteTrace(traceId: string): Promise<void> {
  const url = `${TRACES_BASE_URL}/${encodeURIComponent(traceId)}`;
  const response = await fetch(url, { method: "DELETE" });
  if (response.status === 204) return;
  await assertOk(response);
}

// ============================================================
// Internal helpers
// ============================================================

type QueryValue = string | number | undefined | null | "";

function buildUrl(base: string, params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `${base}?${qs}` : base;
}

async function assertOk(response: Response): Promise<void> {
  if (response.ok) return;

  // Cố parse JSON error body (FastAPI trả {detail: ...}).
  let message = `HTTP ${response.status} ${response.statusText}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") message = body.detail;
  } catch {
    // không parse được → giữ message mặc định
  }
  throw new TraceApiError(response.status, message);
}