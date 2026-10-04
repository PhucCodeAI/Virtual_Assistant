// src/lib/state/mock_seed.ts
//
// DEV SEED — dữ liệu placeholder để UI render trong lúc chờ tích hợp BE.
// TODO: xóa file này khi UI-005 (workspace explorer) hoàn tất.

import type {
  FileNode,
  DiffLine,
  SandboxExecution,
  GitCommit,
} from "./types";

export const SEED_FILE_TREE: FileNode[] = [
  {
    id: "1",
    name: "services",
    path: "services",
    type: "directory",
    status: "clean",
    children: [
      { id: "2", name: "llm_client.py", path: "services/llm_client.py", type: "file", status: "editing" },
      { id: "3", name: "parser.py", path: "services/parser.py", type: "file", status: "clean" },
    ],
  },
  {
    id: "4",
    name: "tests",
    path: "tests",
    type: "directory",
    status: "clean",
    children: [
      { id: "5", name: "test_llm.py", path: "tests/test_llm.py", type: "file", status: "testing" },
    ],
  },
];

export const SEED_DIFF_LINES: DiffLine[] = [
  { type: "same", oldLineNumber: 12, newLineNumber: 12, content: "import httpx" },
  { type: "same", oldLineNumber: 13, newLineNumber: 13, content: "from typing import AsyncGenerator" },
  { type: "del", oldLineNumber: 14, content: "def chat(prompt: str) -> str:" },
  { type: "del", oldLineNumber: 15, content: '    response = httpx.post(URL, json={"prompt": prompt})' },
  { type: "del", oldLineNumber: 16, content: '    return response.json()["text"]' },
  { type: "add", newLineNumber: 14, content: "async def chat(prompt: str) -> AsyncGenerator[str, None]:" },
  { type: "add", newLineNumber: 15, content: "    async with httpx.AsyncClient(timeout=30.0) as client:" },
  { type: "add", newLineNumber: 16, content: '        async with client.stream("POST", URL, json={"prompt": prompt}) as res:' },
  { type: "add", newLineNumber: 17, content: "            async for chunk in res.aiter_text():" },
  { type: "add", newLineNumber: 18, content: "                yield chunk" },
];

export const SEED_SANDBOX: SandboxExecution = {
  command: "pytest tests/test_llm.py -v",
  status: "passed",
  output: [
    "============================= test session starts =============================",
    "rootdir: /workspace, configfile: pyproject.toml",
    "collected 4 items",
    "tests/test_llm.py::test_async_stream_chunks PASSED                     [100%]",
    "============================== 4 passed in 1.42s ==============================",
  ],
  durationMs: 1420,
};

export const SEED_COMMITS: GitCommit[] = [
  {
    hash: "a1b2c3d4e5f6",
    shortHash: "a1b2c3d",
    message: "feat: setup sandbox test pipeline",
    timestamp: "10:00 AM",
    author: "Agent",
    isActive: true,
  },
];