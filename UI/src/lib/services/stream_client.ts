// src/lib/services/stream_client.ts
//
// SSE client v2 — transport layer cho pipeline orchestrator.
//
// Nguyên tắc (UI-002):
//   - fetch + ReadableStream, KHÔNG EventSource.
//   - Idle timeout 45s = 3× heartbeat 15s. Reset mỗi byte nhận được.
//   - cancel() → abort → BE nhận CancelledError → save trace CANCELLED.
//   - KHÔNG auto-retry. Mọi lỗi qua onError, caller quyết định retry.
//
// Trách nhiệm parser/validator thuộc sse_protocol.ts — file này chỉ lo
// transport + lifecycle.

import { parseSSEBlock, toSSEEvent } from "./sse_protocol";
import { ORCHESTRATOR_RUN_URL, ORCHESTRATOR_SYNC_URL } from "./api_config";
import type {
  SSEEvent,
  DoneEventData,
  RunRequest,
  SyncResponse,
} from "$lib/state/types";

// ============================================================
// Public types
// ============================================================

// Q1 UI-002-REPLY: thêm `detail` optional cho debug/UX.
export type StreamErrorReason =
  | "network"
  | "timeout"
  | "aborted"
  | "http_error"
  | "parse_error";

export interface StreamCallbacks {
  onEvent: (event: SSEEvent) => void;
  onError: (reason: StreamErrorReason, detail?: string) => void;
  /** Fire 1 lần khi stream kết thúc (success hoặc fail). `done` null nếu
   *  stream đóng trước khi nhận được event `done`. */
  onComplete: (done: DoneEventData | null) => void;
}

export interface StreamHandle {
  /** Cancel stream. Backend nhận CancelledError → trace lưu CANCELLED. */
  cancel: () => void;
  /** Resolve khi stream đóng hẳn (sau onComplete). */
  done: Promise<void>;
}

export class SyncRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly statusText: string,
  ) {
    super(`HTTP ${status}: ${statusText}`);
    this.name = "SyncRequestError";
  }
}

// ============================================================
// Constants
// ============================================================

const DEFAULT_IDLE_TIMEOUT_MS = 45_000;

// ============================================================
// Public API — stream
// ============================================================

export function runPipelineStream(
  req: RunRequest,
  callbacks: StreamCallbacks,
  options?: { idleTimeoutMs?: number },
): StreamHandle {
  return new PipelineStream(
    req,
    callbacks,
    options?.idleTimeoutMs ?? DEFAULT_IDLE_TIMEOUT_MS,
  );
}

// ============================================================
// Public API — sync
// ============================================================

// Q4 UI-002-REPLY: return SyncResponse thay vì unknown.
export async function runPipelineSync(req: RunRequest): Promise<SyncResponse> {
  const response = await fetch(ORCHESTRATOR_SYNC_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(req),
  });

  if (!response.ok) {
    throw new SyncRequestError(response.status, response.statusText);
  }

  return (await response.json()) as SyncResponse;
}

// ============================================================
// Internal implementation
// ============================================================

class PipelineStream implements StreamHandle {
  private readonly controller = new AbortController();
  private idleTimer: ReturnType<typeof setTimeout> | null = null;
  private cancelled = false;
  private timedOut = false;
  private closed = false;
  readonly done: Promise<void>;

  constructor(
    private readonly req: RunRequest,
    private readonly callbacks: StreamCallbacks,
    private readonly idleTimeoutMs: number,
  ) {
    this.done = this.run();
  }

  cancel(): void {
    if (this.cancelled || this.closed) return;
    this.cancelled = true;
    this.controller.abort();
  }

  // ============================================================
  // Core loop
  // ============================================================

  private async run(): Promise<void> {
    try {
      const response = await fetch(ORCHESTRATOR_RUN_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          "Cache-Control": "no-cache",
        },
        body: JSON.stringify(this.req),
        signal: this.controller.signal,
      });

      if (!response.ok) {
        this.finalizeWithError(
          "http_error",
          `HTTP ${response.status} ${response.statusText}`,
        );
        return;
      }

      if (!response.body) {
        this.finalizeWithError("network", "Response body null — không thể stream");
        return;
      }

      const lastDone = await this.consume(response.body);
      this.closed = true;
      this.callbacks.onComplete(lastDone);
    } catch (err) {
      if (this.closed) return; // đã finalize (abort/timeout/http)
      this.emitErrorFromCatch(err);
    } finally {
      this.clearIdleTimer();
    }
  }

  /**
   * Đọc stream và dispatch từng frame. Trả về DoneEventData nếu nhận được
   * event done, ngược lại null.
   * Throw AbortError khi user cancel hoặc timeout → catch ở run() xử lý.
   */
  private async consume(
    body: ReadableStream<Uint8Array>,
  ): Promise<DoneEventData | null> {
    const reader = body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let lastDone: DoneEventData | null = null;

    this.resetIdleTimer();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        this.resetIdleTimer();
        buffer += decoder.decode(value, { stream: true });

        // SSE frame separator: \n\n (cho phép \r\n\r\n).
        const blocks = buffer.split(/\r?\n\r?\n/);
        buffer = blocks.pop() ?? "";

        for (const block of blocks) {
          const d = this.dispatchBlock(block);
          if (d) lastDone = d;
        }
      }

      // Ticket §4: flush buffer cuối phòng BE close thiếu \n\n.
      // Malformed cuối → dispatchBlock trả null → bỏ qua silent.
      if (buffer.trim()) {
        const d = this.dispatchBlock(buffer);
        if (d) lastDone = d;
      }

      return lastDone;
    } finally {
      reader.releaseLock();
    }
  }

  /**
   * Parse 1 block → dispatch onEvent nếu hợp lệ.
   * Trả về DoneEventData nếu block là event done, ngược lại null.
   */
  private dispatchBlock(block: string): DoneEventData | null {
    const frame = parseSSEBlock(block);
    if (!frame) return null; // comment/heartbeat — bỏ qua

    const event = toSSEEvent(frame.event, frame.data);
    if (!event) return null; // malformed → skip silent (§4)

    this.callbacks.onEvent(event);
    return event.event === "done" ? event.data : null;
  }

  // ============================================================
  // Error handling
  // ============================================================

  private finalizeWithError(reason: StreamErrorReason, detail?: string): void {
    this.closed = true;
    this.callbacks.onError(reason, detail);
    this.callbacks.onComplete(null);
  }

  private emitErrorFromCatch(err: unknown): void {
    if (this.cancelled) {
      this.finalizeWithError("aborted");
      return;
    }
    if (this.timedOut) {
      this.finalizeWithError(
        "timeout",
        `Không nhận byte trong ${this.idleTimeoutMs}ms`,
      );
      return;
    }
    if (err instanceof Error && err.name === "AbortError") {
      // Abort không do user cancel hoặc timeout → coi như network drop.
      this.finalizeWithError("network", err.message);
      return;
    }
    this.finalizeWithError(
      "network",
      err instanceof Error ? err.message : String(err),
    );
  }

  // ============================================================
  // Idle timer
  // ============================================================

  private resetIdleTimer(): void {
    this.clearIdleTimer();
    this.idleTimer = setTimeout(() => {
      this.timedOut = true;
      this.controller.abort();
    }, this.idleTimeoutMs);
  }

  private clearIdleTimer(): void {
    if (this.idleTimer) {
      clearTimeout(this.idleTimer);
      this.idleTimer = null;
    }
  }
}