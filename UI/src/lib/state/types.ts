export type FileStatus = 'clean' | 'target' | 'editing' | 'testing' | 'error';

export interface FileNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  status: FileStatus;
  children?: FileNode[];
}

export interface DiffLine {
  type: 'add' | 'del' | 'same';
  oldLineNumber?: number;
  newLineNumber?: number;
  content: string;
}

export type SandboxStatus = 'idle' | 'running' | 'passed' | 'failed';

export interface SandboxExecution {
  command: string;
  status: SandboxStatus;
  output: string[];
  durationMs: number;
}

export type SSEStatusStep = 'plan' | 'sandbox' | 'test' | 'git';

export interface SSEStatusPayload {
  step: SSEStatusStep;
  message: string;
}

export interface SSETokenPayload {
  delta: string;
}

export interface SSECommitPayload {
  hash: string;
  message: string;
  files: string[];
}

export interface SSEErrorPayload {
  code: string;
  message: string;
}

export interface SSEDonePayload {
  input_token?: number;
  reasoning_token?: number;
  cache_token?: number;
  cached_token?: number;
  total_token?: number;
  output_token?: number;
  total_time?: number;
  cost?: number;
}

export interface CumulativeSessionMetrics {
  inputTokens: number;
  outputTokens: number;
  reasoningTokens: number;
  cachedTokens: number;
  cost: number;
}

export interface GitCommit {
  hash: string;
  shortHash: string;
  message: string;
  timestamp: string;
  author: string;
  isActive: boolean;
  files?: string[];
}

export interface AgentAction {
  id: string;
  step: SSEStatusStep | 'error';
  label: string;
  detail?: string;
  status: 'running' | 'success' | 'failed';
  timestamp: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  latencyMs?: number;
  actions?: AgentAction[];
}