import { sseClient } from '$lib/services/stream_client';
import type {
  FileNode,
  DiffLine,
  SandboxExecution,
  GitCommit,
  AgentAction,
  ChatMessage,
  SSEStatusPayload,
  SSECommitPayload,
  SSEErrorPayload,
  SSEDonePayload,
  CumulativeSessionMetrics
} from './types';

class AgentSessionState {
  panelSizes = $state<[number, number, number]>([20, 40, 40]);

  isStreaming = $state<boolean>(false);
  streamingMessage = $state<string>('');
  currentStep = $state<string>('idle');

  messages = $state<ChatMessage[]>([]);
  activeTurnStartTime = $state<number>(0);

  cumulativeMetrics = $state<CumulativeSessionMetrics>({
    inputTokens: 0,
    outputTokens: 0,
    reasoningTokens: 0,
    cachedTokens: 0,
    cost: 0.0
  });

  fileTree = $state<FileNode[]>([
    {
      id: '1',
      name: 'services',
      path: 'services',
      type: 'directory',
      status: 'clean',
      children: [
        { id: '2', name: 'llm_client.py', path: 'services/llm_client.py', type: 'file', status: 'editing' },
        { id: '3', name: 'parser.py', path: 'services/parser.py', type: 'file', status: 'clean' }
      ]
    },
    {
      id: '4',
      name: 'tests',
      path: 'tests',
      type: 'directory',
      status: 'clean',
      children: [
        { id: '5', name: 'test_llm.py', path: 'tests/test_llm.py', type: 'file', status: 'testing' }
      ]
    }
  ]);

  activeFile = $state<string>('services/llm_client.py');
  activeFileStatus = $state<'Idle' | 'Planning' | 'Patching' | 'Validating' | 'Committed'>('Idle');

  diffLines = $state<DiffLine[]>([
    { type: 'same', oldLineNumber: 12, newLineNumber: 12, content: 'import httpx' },
    { type: 'same', oldLineNumber: 13, newLineNumber: 13, content: 'from typing import AsyncGenerator' },
    { type: 'del',  oldLineNumber: 14, content: 'def chat(prompt: str) -> str:' },
    { type: 'del',  oldLineNumber: 15, content: '    response = httpx.post(URL, json={"prompt": prompt})' },
    { type: 'del',  oldLineNumber: 16, content: '    return response.json()["text"]' },
    { type: 'add',  newLineNumber: 14, content: 'async def chat(prompt: str) -> AsyncGenerator[str, None]:' },
    { type: 'add',  newLineNumber: 15, content: '    async with httpx.AsyncClient(timeout=30.0) as client:' },
    { type: 'add',  newLineNumber: 16, content: '        async with client.stream("POST", URL, json={"prompt": prompt}) as res:' },
    { type: 'add',  newLineNumber: 17, content: '            async for chunk in res.aiter_text():' },
    { type: 'add',  newLineNumber: 18, content: '                yield chunk' }
  ]);

  sandbox = $state<SandboxExecution>({
    command: 'pytest tests/test_llm.py -v',
    status: 'passed',
    output: [
      '============================= test session starts =============================',
      'rootdir: /workspace, configfile: pyproject.toml',
      'collected 4 items',
      'tests/test_llm.py::test_async_stream_chunks PASSED                     [100%]',
      '============================== 4 passed in 1.42s =============================='
    ],
    durationMs: 1420
  });

  actions = $state<AgentAction[]>([]);

  commits = $state<GitCommit[]>([
    {
      hash: 'a1b2c3d4e5f6',
      shortHash: 'a1b2c3d',
      message: 'feat: setup sandbox test pipeline',
      timestamp: '10:00 AM',
      author: 'Agent',
      isActive: true
    }
  ]);

  async sendPrompt(prompt: string) {
    if (this.isStreaming || !prompt.trim()) return;

    const nowStr = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    this.messages.push({
      id: `msg-user-${Date.now()}`,
      role: 'user',
      content: prompt,
      timestamp: nowStr()
    });

    this.isStreaming = true;
    this.streamingMessage = '';
    this.actions = [];
    this.currentStep = 'plan';
    this.activeFileStatus = 'Planning';
    this.activeTurnStartTime = Date.now();

    this.sandbox.status = 'running';
    this.sandbox.output = ['[Sandbox] Initializing isolated container environment...'];

    await sseClient.streamRequest(
      'http://localhost:8000/orchestrator',
      { prompt },
      (eventName, data) => {
        switch (eventName) {
          case 'status': {
            const payload = data as SSEStatusPayload;
            this.currentStep = payload.step;

            if (payload.step === 'plan') this.activeFileStatus = 'Planning';
            if (payload.step === 'sandbox') {
              this.activeFileStatus = 'Patching';
              this.sandbox.output.push(`[Sandbox] ${payload.message}`);
            }
            if (payload.step === 'test') {
              this.activeFileStatus = 'Validating';
              this.sandbox.status = 'running';
              this.sandbox.output.push(`[Test] ${payload.message}`);
            }
            if (payload.step === 'git') {
              this.activeFileStatus = 'Committed';
              this.sandbox.status = 'passed';
            }

            if (this.actions.length > 0) {
              this.actions[this.actions.length - 1].status = 'success';
            }
            this.actions.push({
              id: `act-${Date.now()}-${Math.random()}`,
              step: payload.step,
              label: payload.message,
              status: 'running',
              timestamp: nowStr()
            });
            break;
          }

          case 'token': {
            const payload = data as SSETokenPayload;
            this.streamingMessage += (payload.delta || '');
            break;
          }

          case 'commit': {
            const payload = data as SSECommitPayload;
            if (this.actions.length > 0) {
              this.actions[this.actions.length - 1].status = 'success';
            }
            this.commits = [
              {
                hash: payload.hash,
                shortHash: payload.hash.slice(0, 7),
                message: payload.message,
                timestamp: nowStr(),
                author: 'Agent',
                isActive: true,
                files: payload.files
              },
              ...this.commits.map(c => ({ ...c, isActive: false }))
            ];
            if (payload.files && payload.files.length > 0) {
              this.activeFile = payload.files[0];
            }
            this.activeFileStatus = 'Committed';
            this.sandbox.status = 'passed';
            break;
          }

          case 'error': {
            const payload = data as SSEErrorPayload;
            this.sandbox.status = 'failed';
            this.sandbox.output.push(`[Error: ${payload.code}] ${payload.message}`);
            this.actions.push({
              id: `act-err-${Date.now()}`,
              step: 'error',
              label: `[${payload.code}] ${payload.message}`,
              status: 'failed',
              timestamp: nowStr()
            });
            break;
          }

          case 'done': {
            const payload = data as SSEDonePayload;
            
            const turnLatency = payload.total_time ?? (Date.now() - this.activeTurnStartTime);

            const inTokens = payload.input_token ?? 0;
            const totalTokens = payload.total_token ?? 0;
            
            const outTokens = payload.output_token ?? Math.max(0, totalTokens - inTokens);
            const reasoningTokens = payload.reasoning_token ?? 0;
            const cacheTokens = payload.cache_token ?? payload.cached_token ?? 0;
            const turnCost = payload.cost ?? 0.0;

            this.cumulativeMetrics.inputTokens += inTokens;
            this.cumulativeMetrics.outputTokens += outTokens;
            this.cumulativeMetrics.reasoningTokens += reasoningTokens;
            this.cumulativeMetrics.cachedTokens += cacheTokens;
            this.cumulativeMetrics.cost += turnCost;

            this.sandbox.durationMs = turnLatency;

            if (this.actions.length > 0) {
              this.actions[this.actions.length - 1].status = 'success';
            }

            this.messages.push({
              id: `msg-agent-${Date.now()}`,
              role: 'assistant',
              content: this.streamingMessage,
              timestamp: nowStr(),
              latencyMs: turnLatency,
              actions: [...this.actions]
            });

            this.streamingMessage = '';
            this.isStreaming = false;
            this.currentStep = 'done';
            break;
          }
        }
      },
      (error) => {
        this.sandbox.status = 'failed';
        this.sandbox.output.push(`[Network Failure] ${error.message}`);
        this.actions.push({
          id: `act-net-err-${Date.now()}`,
          step: 'error',
          label: error.message,
          status: 'failed',
          timestamp: nowStr()
        });
        this.isStreaming = false;
      }
    );
  }

  abortCurrentSession() {
    sseClient.abort();
    const turnLatency = Date.now() - this.activeTurnStartTime;

    if (this.streamingMessage) {
      this.messages.push({
        id: `msg-agent-aborted-${Date.now()}`,
        role: 'assistant',
        content: this.streamingMessage + '\n\n*(Quá trình thực thi đã bị người dùng hủy)*',
        timestamp: new Date().toLocaleTimeString(),
        latencyMs: turnLatency
      });
    }

    this.isStreaming = false;
    this.streamingMessage = '';
    this.currentStep = 'aborted';
    this.sandbox.status = 'failed';
  }

  setPanelSizes(sizes: [number, number, number]) {
    this.panelSizes = sizes;
  }
}

export const agentSession = new AgentSessionState();