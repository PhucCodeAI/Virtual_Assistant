// src/lib/services/sse_protocol.ts
//
// SSE protocol layer: parse raw frame → validate → SSEEvent (discriminated union).
//
// Trách nhiệm DUY NHẤT của file này là biến wire format (text) thành type-safe
// SSEEvent. Không chứa logic transport (fetch/reader/abort) — đó là việc của
// stream_client.ts.
//
// Runtime validation là BẮT BUỘC: `SSEEvent` chỉ tồn tại ở compile time.
// JSON.parse trả `unknown` → phải narrow thủ công vì không cài zod (rule #1).
//
// Contract v2 done event đã được BE push (verify 2026-10-04 10:54 qua
// /orchestrator/run/sync response). Legacy shim đã xóa — xem lịch sử
// UI-002-REPLY-3 M2.

import type {
  SSEEvent,
  StatusEventData,
  PlanEventData,
  PlanEventFile,
  FileEventData,
  SandboxEventData,
  TokenEventData,
  CommitEventData,
  ErrorEventData,
  DoneEventData,
  StatusStep,
  FinalStatus,
  FileActionType,
} from "$lib/state/types";

// ============================================================
// Parse SSE frame (per WHATWG spec)
// ============================================================

export interface ParsedSSEFrame {
  event: string;
  data: string;
}

/**
 * Parse 1 SSE block (đã split bằng \n\n) thành { event, data }.
 * Trả null nếu block không chứa `data:` (heartbeat `: ping` hoặc comment-only).
 *
 * Lưu ý spec: sau dấu `:` chỉ bỏ DUY NHẤT 1 space leading.
 * Không dùng .trim() — sẽ strip nhầm trailing space của payload.
 */
export function parseSSEBlock(block: string): ParsedSSEFrame | null {
  let eventName = "message";
  const dataLines: string[] = [];

  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) continue;

    const colon = line.indexOf(":");
    if (colon < 0) continue;

    const field = line.slice(0, colon);
    const rawValue = line.slice(colon + 1);
    const value = rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue;

    if (field === "event") {
      eventName = value;
    } else if (field === "data") {
      dataLines.push(value);
    }
    // id: / retry: bỏ qua — BE không support resume (UI-001-REPLY Q4).
  }

  if (dataLines.length === 0) return null;
  return { event: eventName, data: dataLines.join("\n") };
}

// ============================================================
// Runtime type guards
// ============================================================

const STATUS_STEPS = new Set<string>([
  "plan", "sandbox", "test", "git", "generate", "done",
]);
const FINAL_STATUSES = new Set<string>(["SUCCESS", "FAILED", "CANCELLED"]);
const FILE_ACTIONS = new Set<string>(["create", "update", "delete"]);

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}
function isStatusStep(x: unknown): x is StatusStep {
  return typeof x === "string" && STATUS_STEPS.has(x);
}
function isFinalStatus(x: unknown): x is FinalStatus {
  return typeof x === "string" && FINAL_STATUSES.has(x);
}
function isFileAction(x: unknown): x is FileActionType {
  return typeof x === "string" && FILE_ACTIONS.has(x);
}
function isStringArray(x: unknown): x is string[] {
  return Array.isArray(x) && x.every((v) => typeof v === "string");
}
function num(d: Record<string, unknown>, key: string): number | null {
  const v = d[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
function str(d: Record<string, unknown>, key: string): string | null {
  const v = d[key];
  return typeof v === "string" ? v : null;
}

// ============================================================
// Per-event validators (contract v2 strict)
// ============================================================

function validateStatus(d: Record<string, unknown>): StatusEventData | null {
  if (!isStatusStep(d.step)) return null;
  const message = str(d, "message");
  if (message === null) return null;
  return { step: d.step, message };
}

function validatePlan(d: Record<string, unknown>): PlanEventData | null {
  const explanation = str(d, "explanation");
  if (explanation === null) return null;
  if (!Array.isArray(d.files)) return null;

  const files: PlanEventFile[] = [];
  for (const f of d.files) {
    if (!isRecord(f)) return null;
    if (!str(f, "path")) return null;
    if (!isFileAction(f.action)) return null;
    files.push({ path: f.path as string, action: f.action });
  }

  if (!isStringArray(d.test_command)) return null;
  return { explanation, files, test_command: d.test_command };
}

function validateFile(d: Record<string, unknown>): FileEventData | null {
  const path = str(d, "path");
  if (path === null) return null;
  if (!isFileAction(d.action)) return null;
  const added = num(d, "lines_added");
  const removed = num(d, "lines_removed");
  if (added === null || removed === null) return null;
  return { path, action: d.action, lines_added: added, lines_removed: removed };
}

function validateSandbox(d: Record<string, unknown>): SandboxEventData | null {
  if (!isStringArray(d.command)) return null;
  const exit = num(d, "exit_code");
  const dur = num(d, "duration_ms");
  if (exit === null || dur === null) return null;
  if (typeof d.is_timeout !== "boolean") return null;
  const summary = str(d, "stdout_summary");
  if (summary === null) return null;
  return {
    command: d.command,
    exit_code: exit,
    duration_ms: dur,
    is_timeout: d.is_timeout,
    stdout_summary: summary,
  };
}

function validateToken(d: Record<string, unknown>): TokenEventData | null {
  const delta = str(d, "delta");
  return delta === null ? null : { delta };
}

function validateCommit(d: Record<string, unknown>): CommitEventData | null {
  const hash = str(d, "hash");
  const message = str(d, "message");
  if (hash === null || message === null) return null;
  if (!isStringArray(d.files)) return null;
  return { hash, message, files: d.files };
}

function validateError(d: Record<string, unknown>): ErrorEventData | null {
  const code = str(d, "code");
  const message = str(d, "message");
  if (code === null || message === null) return null;
  return { code, message };
}

function validateDone(d: Record<string, unknown>): DoneEventData | null {
  if (!isFinalStatus(d.status)) return null;

  const duration_ms = num(d, "duration_ms");
  const total_tokens = num(d, "total_tokens");
  const input_tokens = num(d, "input_tokens");
  const output_tokens = num(d, "output_tokens");
  const reasoning_tokens = num(d, "reasoning_tokens");
  const cache_tokens = num(d, "cache_tokens");
  const cost = num(d, "cost");
  const trace_id = str(d, "trace_id");

  if (
    duration_ms === null ||
    total_tokens === null ||
    input_tokens === null ||
    output_tokens === null ||
    reasoning_tokens === null ||
    cache_tokens === null ||
    cost === null ||
    trace_id === null
  ) {
    return null;
  }

  return {
    status: d.status,
    duration_ms,
    total_tokens,
    input_tokens,
    output_tokens,
    reasoning_tokens,
    cache_tokens,
    cost,
    trace_id,
  };
}

// ============================================================
// Public entry point
// ============================================================

/**
 * Chuyển 1 frame SSE (raw) thành SSEEvent đã validate.
 * Trả null nếu JSON hỏng, shape sai, hoặc event name lạ.
 */
export function toSSEEvent(name: string, rawData: string): SSEEvent | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawData);
  } catch {
    return null;
  }
  if (!isRecord(parsed)) return null;

  switch (name) {
    case "status": {
      const d = validateStatus(parsed);
      return d ? { event: "status", data: d } : null;
    }
    case "plan": {
      const d = validatePlan(parsed);
      return d ? { event: "plan", data: d } : null;
    }
    case "file": {
      const d = validateFile(parsed);
      return d ? { event: "file", data: d } : null;
    }
    case "sandbox": {
      const d = validateSandbox(parsed);
      return d ? { event: "sandbox", data: d } : null;
    }
    case "token": {
      const d = validateToken(parsed);
      return d ? { event: "token", data: d } : null;
    }
    case "commit": {
      const d = validateCommit(parsed);
      return d ? { event: "commit", data: d } : null;
    }
    case "error": {
      const d = validateError(parsed);
      return d ? { event: "error", data: d } : null;
    }
    case "done": {
      const d = validateDone(parsed);
      return d ? { event: "done", data: d } : null;
    }
    default:
      return null;
  }
}