// src/lib/state/pipeline_steps.ts
//
// Helper tính trạng thái từng bước pipeline từ statusHistory.
//
// Q2 UI-FINAL-REPLY: pure function, không phụ thuộc agentSession.
// Input tối thiểu: statusHistory[] + finalStatus + hasError.
//
// Logic (theo UI-FINAL §UI-003):
//   - Step trước step cuối cùng xuất hiện: "done"
//   - Step cuối cùng xuất hiện: "active" nếu pipeline đang chạy,
//                                "failed" nếu terminal error/cancel
//   - Step sau step cuối cùng: "pending"

import type { StatusStep, FinalStatus } from "./types";

export type StepState = "pending" | "active" | "done" | "failed";

export type StepStateMap = Record<StatusStep, StepState>;

// Thứ tự pipeline theo contract v2. "done" không phải step bước —
// là terminal marker. Đưa vào để Record đủ key.
const STEP_ORDER: StatusStep[] = [
  "plan",
  "generate",
  "sandbox",
  "test",
  "git",
  "done",
];

const PENDING_MAP: StepStateMap = {
  plan: "pending",
  generate: "pending",
  sandbox: "pending",
  test: "pending",
  git: "pending",
  done: "pending",
};

/**
 * Tính trạng thái từng step.
 *
 * @param statusHistory - Chuỗi StatusStep theo thứ tự event đến.
 * @param finalStatus   - FinalStatus nếu pipeline đã kết thúc (done event).
 * @param hasError      - true nếu có event "error" trong session.
 */
export function computeStepStates(
  statusHistory: StatusStep[],
  finalStatus: FinalStatus | null,
  hasError: boolean,
): StepStateMap {
  if (statusHistory.length === 0) return { ...PENDING_MAP };

  // Bước cuối cùng đã thấy. Bỏ "done" — không phải pipeline step.
  const reached = statusHistory.filter((s) => s !== "done");
  if (reached.length === 0) {
    // Chỉ có "done" trong history — pipeline chạy thẳng tới cuối không
    // emit step nào khác (edge case). Mọi thứ coi như done.
    return { ...PENDING_MAP, done: "done" };
  }

  const lastStep = reached[reached.length - 1];
  const lastIdx = STEP_ORDER.indexOf(lastStep);

  const failed = hasError || finalStatus === "FAILED" || finalStatus === "CANCELLED";
  const terminal = finalStatus !== null;

  const result: StepStateMap = { ...PENDING_MAP };

  for (let i = 0; i < STEP_ORDER.length; i++) {
    const step = STEP_ORDER[i];
    if (i < lastIdx) {
      result[step] = "done";
    } else if (i === lastIdx) {
      result[step] = failed ? "failed" : terminal ? "done" : "active";
    } else {
      result[step] = "pending";
    }
  }

  // Marker terminal: đánh dấu "done" step của map khi pipeline kết thúc SUCCESS.
  if (finalStatus === "SUCCESS") result.done = "done";

  return result;
}