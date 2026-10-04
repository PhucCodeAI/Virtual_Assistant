// UI/src/lib/state/types/index.ts
//
// Barrel export. QUY TẮC:
//   - Chỉ re-export type + runtime value thuộc domain "types".
//   - KHÔNG re-export component / Svelte rune / service.
//   - KHÔNG chứa logic. Cần logic → tạo module riêng.
//
// Import path từ ngoài: `import type { ... } from "$lib/state/types"`.

export * from "./contract";   // type-only
export * from "./ui";         // type-only
export * from "./errors";     // runtime: ERROR_MESSAGES_VI, getErrorMessage