// UI/src/lib/state/types/contract.ts
//
// BACKEND CONTRACT v2
// Sync point: UI-001-REPLY-3 (2026-10-04)
// BE commit: <pending — update khi BE push vào thread UI-001-REPLY-3>
//
// QUY TẮC:
//   - File này mirror 1:1 contract từ Backend/dtos/orchestrator.py
//   - KHÔNG tự thêm/bớt field mà không có ticket BE approve
//   - Khi BE đổi contract → BE mở ticket [UI-XXX] update file này
//   - UI-only type đặt trong ui.ts, KHÔNG trộn vào đây
//
// @backend-not-yet-shipped: CANCELLED & SyncResponse.status removal
// BE commit pending in ticket thread UI-001-REPLY-3.
// Safe to compile; integration test after BE push.

// ============================================================
// Enum / Literal types
// ============================================================

export type StatusStep =
  | "plan"
  | "sandbox"
  | "test"
  | "git"
  | "generate"
  | "done";

// Q2 (UI-001-REPLY): CANCELLED added. Không phải FAILED — user chủ động stop.
// UI semantics: CANCELLED = ⏹️ xám, ẩn commit link; FAILED = ❌ đỏ, error banner.
export type FinalStatus = "SUCCESS" | "FAILED" | "CANCELLED";

export type FileActionType = "create" | "update" | "delete";

// "internal" là reserved — BE chưa emit span nào loại này (Q6 UI-001-REPLY).
// FE dùng icon trung tính (⚙️) khi gặp.
export type SpanType = "llm" | "tool" | "sandbox" | "git" | "internal";

export type SpanStatus = "OK" | "ERROR";

// ============================================================
// SSE Event Payloads
// ============================================================

export interface StatusEventData {
  step: StatusStep;
  message: string;
}

export interface PlanEventFile {
  path: string;
  action: FileActionType;
}

export interface PlanEventData {
  explanation: string;
  files: PlanEventFile[];
  test_command: string[];
}

export interface FileEventData {
  path: string;
  action: FileActionType;
  lines_added: number;
  lines_removed: number;
}

export interface SandboxEventData {
  command: string[];
  exit_code: number;
  duration_ms: number;
  is_timeout: boolean;
  stdout_summary: string;
}

export interface TokenEventData {
  delta: string;
}

export interface CommitEventData {
  hash: string;
  message: string;
  files: string[];
}

// code: string (open) — BE từ chối closed enum (Q3 UI-001-REPLY).
// FE map sang message tiếng Việt ở errors.ts qua KnownErrorCode union.
export interface ErrorEventData {
  code: string;
  message: string;
}

export interface DoneEventData {
  status: FinalStatus;
  duration_ms: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  cache_tokens: number;
  cost: number;
  trace_id: string;
}

// ============================================================
// SSE Event — Discriminated Union
//
// Q4 (UI-001-REPLY): BE KHÔNG support reconnection. Field `id` do BE emit
// nhưng luôn None → không đưa vào type này. FE dùng fetch + ReadableStream,
// KHÔNG dùng EventSource (EventSource tự retry → trigger pipeline mới → tốn
// token). Khi mất kết nối → banner "Kết nối đứt", KHÔNG auto-retry.
// ============================================================

export type SSEEvent =
  | { event: "status";  data: StatusEventData }
  | { event: "plan";    data: PlanEventData }
  | { event: "file";    data: FileEventData }
  | { event: "sandbox"; data: SandboxEventData }
  | { event: "token";   data: TokenEventData }
  | { event: "commit";  data: CommitEventData }
  | { event: "error";   data: ErrorEventData }
  | { event: "done";    data: DoneEventData };

// Helper cho tầng service (stream_client.ts). KHÔNG dùng ở component.
// Lý do: component không nên tự viết `evt.event === "..."` rải rác.
export type SSEEventName = SSEEvent["event"];
export type SSEEventOf<T extends SSEEventName> = Extract<SSEEvent, { event: T }>;

// ============================================================
// REST API — Request
// ============================================================

export interface RunRequest {
  prompt: string;
  session_id?: string | null;
}

// ============================================================
// REST API — Trace
// ============================================================

export interface SpanDTO {
  span_id: string;
  name: string;
  span_type: SpanType;
  duration_ms: number;
  start_offset_ms: number;
  status: SpanStatus;
  input_data: unknown;
  output_data: unknown;
  metadata: Record<string, unknown>;
}

// Q1 (UI-001-REPLY): status: FinalStatus. BE không insert RUNNING —
// pipeline < 30s, insert 1 lần khi xong. GET /traces/{id} giữa chừng → 404.
export interface TraceSummary {
  trace_id: string;
  session_id: string;
  prompt: string;
  status: FinalStatus;
  duration_ms: number;
  total_tokens: number;
  cost: number;
  created_at: string;
}

export interface TraceDetail extends TraceSummary {
  input_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  cache_tokens: number;
  error_message: string | null;
  finished_at: string | null;
  spans: SpanDTO[];
  metadata?: Record<string, unknown>;
}

// ============================================================
// REST API — Sync response
//
// Q5 (UI-001-REPLY): bỏ field `status` top-level — trùng semantic với
// done.status. FE đọc `response.done?.status`.
// Edge case: done === null → coi như FAILED (chưa từng xảy ra trong test).
// ============================================================

export interface SyncResponse {
  trace_id: string | null;
  plan: PlanEventData | null;
  file_events: FileEventData[];
  sandbox_events: SandboxEventData[];
  commit: CommitEventData | null;
  done: DoneEventData | null;
  errors: ErrorEventData[];
}

// ============================================================
// REST API — Error
// ============================================================

export interface ApiErrorDetail {
  code: string;
  message: string;
}