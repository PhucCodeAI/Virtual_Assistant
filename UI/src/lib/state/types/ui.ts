// UI/src/lib/state/types/ui.ts
//
// UI-ONLY TYPES
// FE sở hữu, KHÔNG cần ticket BE. Refactor tự do.
// Nếu type trong đây được promote thành contract → mở ticket BE.
//
// Import type từ contract.ts được phép (ui → contract: OK).
// KHÔNG BAO GIỜ import ngược (contract → ui).

import type { StatusStep } from "./contract";

// ============================================================
// File Explorer
// ============================================================

export type FileStatus = "clean" | "target" | "editing" | "testing" | "error";

export interface FileNode {
  id: string;
  name: string;
  path: string;
  type: "file" | "directory";
  status: FileStatus;
  children?: FileNode[];
}

// ============================================================
// Diff Viewer
// ============================================================

export type DiffLineType = "add" | "del" | "same";

export interface DiffLine {
  type: DiffLineType;
  oldLineNumber?: number;
  newLineNumber?: number;
  content: string;
}

// ============================================================
// Sandbox panel
// ============================================================

export type SandboxStatus = "idle" | "running" | "passed" | "failed" | "cancelled";

export interface SandboxExecution {
  command: string;
  status: SandboxStatus;
  output: string[];
  durationMs: number;
}

// ============================================================
// Session metrics (client-side accumulation)
// ============================================================

export interface CumulativeSessionMetrics {
  inputTokens: number;
  outputTokens: number;
  reasoningTokens: number;
  cachedTokens: number;
  cost: number;
}

// ============================================================
// Git panel
// ============================================================

export interface GitCommit {
  hash: string;
  shortHash: string;
  message: string;
  timestamp: string;
  author: string;
  isActive: boolean;
  files?: string[];
}

// ============================================================
// Agent timeline (chat panel)
//
// Q3 (UI-001-REPLY): BE không có StatusStep "error". FE tự thêm sentinel
// "error" cho AgentAction — KHÔNG đẩy ngược vào contract.
// FE suy ra trạng thái step từ event cuối cùng (computeStepStates trong
// agent_session.svelte.ts — sẽ implement ở UI-003).
// ============================================================

export type AgentActionStep = StatusStep | "error";

export type AgentActionStatus = "running" | "success" | "failed";

export interface AgentAction {
  id: string;
  step: AgentActionStep;
  label: string;
  detail?: string;
  status: AgentActionStatus;
  timestamp: string;
}

// ============================================================
// Chat
// ============================================================

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  latencyMs?: number;
  actions?: AgentAction[];
}

// ============================================================
// Error codes (client-side catalog)
//
// Q3 (UI-001-REPLY): contract giữ `code: string`. FE tạo KnownErrorCode
// union cho autocomplete + mapping message.
// Open union pattern: `KnownErrorCode | (string & {})` giữ autocomplete
// mà KHÔNG break compile khi BE emit code mới chưa sync catalog.
// ============================================================

export type KnownErrorCode =
  // LLM
  | "LLM_ERROR"
  | "LLM_RESPONSE_INVALID"
  | "LLM_SCHEMA_MISMATCH"
  | "LLM_STREAM_BROKEN"
  // Workspace
  | "WORKSPACE_ERROR"
  | "WORKSPACE_PATH_UNSAFE"
  | "WORKSPACE_EDIT_FAILED"
  | "WORKSPACE_FILE_NOT_FOUND"
  // Sandbox
  | "SANDBOX_ERROR"
  | "SANDBOX_DOCKER_UNAVAILABLE"
  | "SANDBOX_TIMEOUT"
  // Git
  | "GIT_ERROR"
  | "GIT_COMMAND_FAILED"
  // Trace
  | "TRACE_ERROR"
  | "TRACE_STORAGE_UPLOAD_FAILED"
  | "TRACE_STORAGE_DOWNLOAD_FAILED"
  | "TRACE_METADATA_WRITE_FAILED"
  | "TRACE_NOT_FOUND"
  | "TRACE_RECORD_EMPTY"
  | "TRACE_QUERY_FAILED"
  | "TRACE_RESPONSE_INVALID"
  | "TRACE_BLOB_PATH_INVALID"
  | "TRACE_DELETE_FAILED"
  | "TRACE_COUNT_FAILED"
  | "TRACE_STORAGE_DELETE_FAILED"
  | "TRACE_STORAGE_LIST_FAILED"
  // Orchestrator
  | "TEST_MAX_RETRIES"
  | "SYSTEM_ERROR";

// Open union — nhận mọi string. Không collapse về `string` nhờ `(string & {})`.
export type ErrorCode = KnownErrorCode | (string & {});

export type SessionPhase = "idle" | StatusStep | "aborted" | "error";

// ============================================================
// File explorer — active file UI state
// ============================================================

export type ActiveFileStatus =
  | "Idle"
  | "Planning"
  | "Patching"
  | "Validating"
  | "Committed";