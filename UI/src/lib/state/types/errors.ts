// UI/src/lib/state/types/errors.ts
//
// Runtime artifacts cho error handling.
// KHÔNG đặt trong contract.ts (contract chỉ chứa type).
// KHÔNG đặt trong ui.ts (giữ ui.ts type-only để barrel có thể `export type *`).

import type { KnownErrorCode } from "./ui";

// Catalog message tiếng Việt. Sync với BE khi BE thêm error code mới
// (BE reply vào ticket tương ứng, FE update file này — non-breaking).
export const ERROR_MESSAGES_VI: Record<KnownErrorCode, string> = {
  // LLM
  LLM_ERROR: "Lỗi gọi mô hình ngôn ngữ. Vui lòng thử lại.",
  LLM_RESPONSE_INVALID: "Mô hình trả về dữ liệu không hợp lệ.",
  LLM_SCHEMA_MISMATCH: "Dữ liệu trả về không đúng định dạng yêu cầu.",
  LLM_STREAM_BROKEN: "Kết nối stream bị đứt giữa chừng.",

  // Workspace
  WORKSPACE_ERROR: "Lỗi thao tác trên workspace.",
  WORKSPACE_PATH_UNSAFE: "Đường dẫn file không an toàn.",
  WORKSPACE_EDIT_FAILED: "Không thể áp dụng chỉnh sửa vào file.",
  WORKSPACE_FILE_NOT_FOUND: "File không tồn tại trong workspace.",

  // Sandbox
  SANDBOX_ERROR: "Lỗi sandbox.",
  SANDBOX_DOCKER_UNAVAILABLE: "Docker không khả dụng.",
  SANDBOX_TIMEOUT: "Quá thời gian chạy test.",

  // Git
  GIT_ERROR: "Lỗi thao tác git.",
  GIT_COMMAND_FAILED: "Lệnh git thất bại.",

  // Trace
  TRACE_ERROR: "Lỗi xử lý trace.",
  TRACE_STORAGE_UPLOAD_FAILED: "Không thể upload trace lên storage.",
  TRACE_STORAGE_DOWNLOAD_FAILED: "Không thể tải trace từ storage.",
  TRACE_METADATA_WRITE_FAILED: "Không thể ghi metadata của trace.",
  TRACE_NOT_FOUND: "Không tìm thấy trace.",
  TRACE_RECORD_EMPTY: "Trace không có dữ liệu.",
  TRACE_QUERY_FAILED: "Truy vấn trace thất bại.",
  TRACE_RESPONSE_INVALID: "Dữ liệu trace trả về không hợp lệ.",
  TRACE_BLOB_PATH_INVALID: "Đường dẫn blob của trace không hợp lệ.",
  TRACE_DELETE_FAILED: "Không thể xoá trace.",
  TRACE_COUNT_FAILED: "Không thể đếm số lượng trace.",
  TRACE_STORAGE_DELETE_FAILED: "Không thể xoá trace khỏi storage.",
  TRACE_STORAGE_LIST_FAILED: "Không thể liệt kê trace từ storage.",

  // Orchestrator
  TEST_MAX_RETRIES: "Đã thử sửa lỗi nhiều lần nhưng test vẫn fail.",
  SYSTEM_ERROR: "Lỗi hệ thống không mong đợi."
};

/**
 * Tra message tiếng Việt từ error code.
 * Fallback `Lỗi không xác định (CODE)` khi BE emit code chưa sync catalog.
 */
export function getErrorMessage(code: string): string {
  const known = ERROR_MESSAGES_VI as Record<string, string | undefined>;
  return known[code] ?? `Lỗi không xác định (${code})`;
}