export type Tag = {
  id: number;
  label: string;
}

export type Memory = {
  id: number;
  memory: string;
  image: string | null;
  created_at: string;
  tags?: string[];
}

export const MODES = {
  SEARCH: "search",
  CHAT: "chat",
  AGENT: "agent",
} as const;

export type Mode = typeof MODES[keyof typeof MODES];

export interface ThinkingBlock {
  content: string;
  isComplete: boolean;
}

export interface AssistantThinking {
  [assistantName: string]: ThinkingBlock[];
}

export interface SubagentState {
  name: string;
  chat: string;
  thinkingBlocks: ThinkingBlock[];
  toolCalls: ToolCallState[];
}

export interface ToolCallState {
  id: string;
  toolName: string;
  state: "loading" | "ready" | "error" | "default";
  input?: unknown;
  output?: unknown;
  subagent?: SubagentState;
}

export type StreamSource =
  | "assistant"
  | "assistant_thinking"
  | "subagent"
  | "subagent_thinking"
  | "assistant_tool"
  | "subagent_tool"
  | "system";

export interface StreamEventItem {
  id: string;
  source: StreamSource;
  label: string;
  token: string;
  timestamp: number;
  kind: "default" | "tool_call_request" | "tool_call_response";
  toolName?: string;
  toolCallId?: string;
  parentToolName?: string;
  payload?: unknown;
}

export type SSEEvent =
  | { type: "assistant_token"; token: string; source: StreamSource }
  | { type: "thinking_token"; token: string; source: StreamSource }
  | { type: "thinking_complete"; source: StreamSource }
  | { type: "subagent_thinking_token"; tool_name: string; token: string; source: StreamSource }
  | { type: "subagent_thinking_complete"; tool_name: string; source: StreamSource }
  | { type: "subagent_token"; tool_name: string; token: string; source: StreamSource }
  | { type: "assistant_tool_call_start"; call_id: string; tool_name: string; input?: unknown; source: StreamSource }
  | { type: "assistant_tool_call_end"; call_id: string; tool_name: string; output?: unknown; source: StreamSource }
  | { type: "subagent_tool_call_start"; call_id: string; parent_tool_name: string; tool_name: string; input?: unknown; source: StreamSource }
  | { type: "subagent_tool_call_end"; call_id: string; parent_tool_name: string; tool_name: string; output?: unknown; source: StreamSource }
  | { type: "end"; source: StreamSource }
  | { type: "error"; message: string; source: StreamSource };
