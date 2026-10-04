// src/lib/state/agent_session.svelte.ts
//
// Singleton state cho 1 phiên chạy pipeline. Sử dụng Svelte 5 runes ($state).
//
// Trách nhiệm:
//   - Giữ state hiển thị (chat, sandbox, metrics, actions, commits).
//   - Điều phối stream từ stream_client (runPipelineStream).
//   - Dispatch SSEEvent → handler riêng cho từng loại (exhaustiveness check).
//   - Accumulate typed event history cho panel riêng (fileEvents, sandboxEvents).
//
// Transport lifecycle (UI-002): streamHandle.cancel() → onError("aborted")
// → finalizeAborted(). Timeout/network/http_error → finalizeWithError().
//
// UI-003: bổ sung 7 state mới (currentPlan, fileEvents, sandboxEvents,
// lastCommit, lastDone, currentStatus, lastError) + statusHistory cho
// computeStepStates. Giữ actions[] cho chat timeline — mục đích khác.

import {
  runPipelineStream,
  type StreamHandle,
  type StreamErrorReason,
} from "$lib/services/stream_client";
import { getErrorMessage } from "$lib/state/types/errors";
import { computeStepStates, type StepStateMap } from "./pipeline_steps";
import type {
  RunRequest,
  SSEEvent,
  StatusEventData,
  PlanEventData,
  FileEventData,
  SandboxEventData,
  TokenEventData,
  CommitEventData,
  ErrorEventData,
  DoneEventData,
  StatusStep,
  FileNode,
  DiffLine,
  SandboxExecution,
  GitCommit,
  AgentAction,
  AgentActionStatus,
  ChatMessage,
  CumulativeSessionMetrics,
  SessionPhase,
  ActiveFileStatus,
} from "$lib/state/types";
import {
  SEED_FILE_TREE,
  SEED_DIFF_LINES,
  SEED_SANDBOX,
  SEED_COMMITS,
} from "./mock_seed";

// ============================================================
// Helpers
// ============================================================

function nextId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function nowTime(): string {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// ============================================================
// State class
// ============================================================

class AgentSessionState {
  // ---- Layout ----
  panelSizes = $state<[number, number, number]>([20, 40, 40]);

  // ---- Pipeline lifecycle ----
  isStreaming = $state<boolean>(false);
  currentStep = $state<SessionPhase>("idle");
  streamingMessage = $state<string>("");
  activeTurnStartTime = $state<number>(0);

  // ---- Typed event history (UI-003) ----
  currentPlan = $state<PlanEventData | null>(null);
  fileEvents = $state<FileEventData[]>([]);
  sandboxEvents = $state<SandboxEventData[]>([]);
  lastCommit = $state<CommitEventData | null>(null);
  lastDone = $state<DoneEventData | null>(null);
  lastError = $state<ErrorEventData | null>(null);

  /** Chuỗi StatusStep theo thứ tự event — input cho computeStepStates. */
  statusHistory = $state<StatusStep[]>([]);

  /** Derived — map trạng thái từng bước pipeline. */
  stepStates = $derived<StepStateMap>(
    computeStepStates(
      this.statusHistory,
      this.lastDone?.status ?? null,
      this.lastError !== null,
    ),
  );

  // ---- Chat ----
  messages = $state<ChatMessage[]>([]);

  // ---- Metrics ----
  cumulativeMetrics = $state<CumulativeSessionMetrics>({
    inputTokens: 0,
    outputTokens: 0,
    reasoningTokens: 0,
    cachedTokens: 0,
    cost: 0,
  });

  // ---- Workspace (dev seed — xóa khi tích hợp BE) ----
  fileTree = $state<FileNode[]>(SEED_FILE_TREE);
  activeFile = $state<string>("services/llm_client.py");
  activeFileStatus = $state<ActiveFileStatus>("Idle");
  diffLines = $state<DiffLine[]>(SEED_DIFF_LINES);

  // ---- Sandbox (mirror của entry mới nhất trong sandboxEvents) ----
  sandbox = $state<SandboxExecution>(SEED_SANDBOX);

  // ---- Actions (timeline gắn vào ChatMessage) ----
  actions = $state<AgentAction[]>([]);

  // ---- Commits ----
  commits = $state<GitCommit[]>(SEED_COMMITS);

  // ---- Stream handle (private) ----
  private streamHandle: StreamHandle | null = null;

  // ============================================================
  // Public API
  // ============================================================

  async sendPrompt(prompt: string): Promise<void> {
    const trimmed = prompt.trim();
    if (this.isStreaming || !trimmed) return;

    this.messages.push({
      id: nextId("msg-user"),
      role: "user",
      content: trimmed,
      timestamp: nowTime(),
    });

    // Reset toàn bộ state của phiên mới.
    this.resetTurnState();

    this.isStreaming = true;
    this.activeTurnStartTime = Date.now();
    this.sandbox.status = "running";
    this.sandbox.output = ["[Sandbox] Đang khởi tạo môi trường..."];

    this.streamHandle = runPipelineStream(
      { prompt: trimmed } satisfies RunRequest,
      {
        onEvent: (evt) => this.handleEvent(evt),
        onError: (reason, detail) => this.handleStreamError(reason, detail),
        onComplete: (done) => this.handleStreamComplete(done),
      },
    );
  }

  /**
   * Nút Stop. Backend nhận CancelledError → save trace CANCELLED.
   * Client side: onError("aborted") sẽ fire → finalizeAborted().
   */
  abortCurrentSession(): void {
    if (!this.streamHandle) return;
    this.streamHandle.cancel();
  }

  setPanelSizes(sizes: [number, number, number]): void {
    this.panelSizes = sizes;
  }

  // ============================================================
  // Reset — bắt đầu phiên mới
  // ============================================================

  private resetTurnState(): void {
    this.streamingMessage = "";
    this.actions = [];
    this.currentStep = "plan";
    this.activeFileStatus = "Planning";

    this.currentPlan = null;
    this.fileEvents = [];
    this.sandboxEvents = [];
    this.lastCommit = null;
    this.lastDone = null;
    this.lastError = null;
    this.statusHistory = [];
  }

  // ============================================================
  // Event dispatcher — exhaustiveness check
  // ============================================================

  private handleEvent(evt: SSEEvent): void {
    switch (evt.event) {
      case "status":  return this.onStatus(evt.data);
      case "plan":    return this.onPlan(evt.data);
      case "file":    return this.onFile(evt.data);
      case "sandbox": return this.onSandbox(evt.data);
      case "token":   return this.onToken(evt.data);
      case "commit":  return this.onCommit(evt.data);
      case "error":   return this.onSseError(evt.data);
      case "done":    return this.onDone(evt.data);
      default: {
        const _exhaustive: never = evt;
        void _exhaustive;
      }
    }
  }

  // ============================================================
  // Transport lifecycle
  // ============================================================

  private handleStreamError(reason: StreamErrorReason, detail?: string): void {
    switch (reason) {
      case "aborted":
        this.finalizeAborted();
        break;
      case "timeout":
        this.finalizeWithError(
          detail ?? "Kết nối đứt (không có tín hiệu trong 45s). Vui lòng gửi lại prompt.",
        );
        break;
      case "network":
        this.finalizeWithError(detail ?? "Lỗi kết nối mạng.");
        break;
      case "http_error":
        this.finalizeWithError(detail ?? "Lỗi server.");
        break;
      case "parse_error":
        this.finalizeWithError("Dữ liệu stream không hợp lệ.");
        break;
      default: {
        const _exhaustive: never = reason;
        void _exhaustive;
      }
    }
  }

  private handleStreamComplete(done: DoneEventData | null): void {
    this.streamHandle = null;
    if (!this.isStreaming) return;
    // Stream đóng mà onDone chưa fire → coi như FAILED (edge case).
    void done;
    this.finalizeWithError("Stream kết thúc bất thường.");
  }

  // ============================================================
  // Finalizers
  // ============================================================

  private finalizeAborted(): void {
    const latency = Date.now() - this.activeTurnStartTime;

    if (this.streamingMessage) {
      this.messages.push({
        id: nextId("msg-abort"),
        role: "assistant",
        content: this.streamingMessage + "\n\n*(Đã dừng bởi người dùng)*",
        timestamp: nowTime(),
        latencyMs: latency,
      });
    }

    this.streamHandle = null;
    this.isStreaming = false;
    this.streamingMessage = "";
    this.currentStep = "aborted";
    this.sandbox.status = "cancelled";
    this.sandbox.output.push("[Cancelled] Người dùng đã dừng phiên.");
  }

  private finalizeWithError(message: string): void {
    this.streamHandle = null;
    this.sandbox.status = "failed";
    this.sandbox.output.push(`[Network] ${message}`);
    this.markLastAction("failed");
    this.actions.push({
      id: nextId("net"),
      step: "error",
      label: message,
      status: "failed",
      timestamp: nowTime(),
    });

    this.currentStep = "error";
    this.isStreaming = false;
    this.streamingMessage = "";
  }

  // ============================================================
  // Per-event handlers
  // ============================================================

  private onStatus(d: StatusEventData): void {
    this.currentStep = d.step;
    this.statusHistory.push(d.step);

    switch (d.step) {
      case "plan":
        this.activeFileStatus = "Planning";
        break;
      case "generate":
        this.activeFileStatus = "Patching";
        break;
      case "sandbox":
        this.activeFileStatus = "Patching";
        this.sandbox.output.push(`[Sandbox] ${d.message}`);
        break;
      case "test":
        this.activeFileStatus = "Validating";
        this.sandbox.status = "running";
        this.sandbox.output.push(`[Test] ${d.message}`);
        break;
      case "git":
        this.activeFileStatus = "Committed";
        break;
      case "done":
        break;
      default: {
        const _exhaustive: never = d.step;
        void _exhaustive;
      }
    }

    this.markLastAction("success");
    this.actions.push({
      id: nextId("act"),
      step: d.step,
      label: d.message,
      status: "running",
      timestamp: nowTime(),
    });
  }

  private onPlan(d: PlanEventData): void {
    this.currentPlan = d;

    const fileList = d.files.map((f) => `${f.action} ${f.path}`).join("\n");
    this.actions.push({
      id: nextId("plan"),
      step: "plan",
      label: `Kế hoạch: ${d.explanation}`,
      detail: fileList,
      status: "running",
      timestamp: nowTime(),
    });
  }

  private onFile(d: FileEventData): void {
    this.fileEvents.push(d);
    this.activeFile = d.path;

    const delta = d.lines_added - d.lines_removed;
    const deltaStr = delta >= 0 ? `+${delta}` : String(delta);
    this.actions.push({
      id: nextId("file"),
      step: "generate",
      label: `${d.action} ${d.path} (${deltaStr})`,
      status: "success",
      timestamp: nowTime(),
    });
  }

  private onSandbox(d: SandboxEventData): void {
    this.sandboxEvents.push(d);

    // Mirror entry mới nhất vào panel sandbox chính.
    const cmd = d.command.join(" ");
    this.sandbox.command = cmd;
    this.sandbox.durationMs = d.duration_ms;
    this.sandbox.output.push(
      `$ ${cmd}`,
      d.stdout_summary,
      `[exit=${d.exit_code}${d.is_timeout ? " TIMEOUT" : ""}]`,
    );
    this.sandbox.status =
      d.exit_code === 0 && !d.is_timeout ? "passed" : "failed";
  }

  private onToken(d: TokenEventData): void {
    this.streamingMessage += d.delta;
  }

  private onCommit(d: CommitEventData): void {
    this.lastCommit = d;
    this.markLastAction("success");
    this.commits = [
      {
        hash: d.hash,
        shortHash: d.hash.slice(0, 7),
        message: d.message,
        timestamp: nowTime(),
        author: "Agent",
        isActive: true,
        files: d.files,
      },
      ...this.commits.map((c) => ({ ...c, isActive: false })),
    ];
    if (d.files.length > 0) this.activeFile = d.files[0];
    this.activeFileStatus = "Committed";
    this.sandbox.status = "passed";
  }

  private onSseError(d: ErrorEventData): void {
    this.lastError = d;

    const friendly = getErrorMessage(d.code);
    this.sandbox.status = "failed";
    this.sandbox.output.push(`[Error: ${d.code}] ${friendly}`);
    this.markLastAction("failed");
    this.actions.push({
      id: nextId("err"),
      step: "error",
      label: friendly,
      detail: d.message,
      status: "failed",
      timestamp: nowTime(),
    });
    this.currentStep = "error";
  }

  private onDone(d: DoneEventData): void {
    this.lastDone = d;

    this.cumulativeMetrics.inputTokens += d.input_tokens;
    this.cumulativeMetrics.outputTokens += d.output_tokens;
    this.cumulativeMetrics.reasoningTokens += d.reasoning_tokens;
    this.cumulativeMetrics.cachedTokens += d.cache_tokens;
    this.cumulativeMetrics.cost += d.cost;

    this.sandbox.durationMs = d.duration_ms;

    this.markLastAction(d.status === "SUCCESS" ? "success" : "failed");

    this.messages.push({
      id: nextId("msg-agent"),
      role: "assistant",
      content: this.streamingMessage,
      timestamp: nowTime(),
      latencyMs: d.duration_ms,
      actions: [...this.actions],
    });

    this.streamingMessage = "";
    this.isStreaming = false;

    // Phân loại terminal state theo FinalStatus.
    switch (d.status) {
      case "SUCCESS":
        this.currentStep = "done";
        break;
      case "CANCELLED":
        this.currentStep = "aborted";
        this.sandbox.status = "cancelled";
        break;
      case "FAILED":
        this.currentStep = "error";
        break;
      default: {
        const _exhaustive: never = d.status;
        void _exhaustive;
      }
    }
  }

  // ============================================================
  // Utilities
  // ============================================================

  private markLastAction(status: AgentActionStatus): void {
    const last = this.actions[this.actions.length - 1];
    if (last) last.status = status;
  }
}

export const agentSession = new AgentSessionState();