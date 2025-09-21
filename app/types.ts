export type Memory = {
  id: number;
  memory: string;
  image: string | null;
  created_at: string;
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

export type SSEEvent =
  | { type: "assistant_token"; token: string }
  | { type: "thinking_token"; token: string }
  | { type: "thinking_complete" }
  | { type: "subagent_thinking_token"; tool_name: string; token: string }
  | { type: "subagent_thinking_complete"; tool_name: string }
  | { type: "subagent_token"; tool_name: string; token: string }
  | { type: "tool_call_start"; tool_name: string; input?: unknown } // legacy
  | { type: "tool_call_end"; tool_name: string; output?: unknown } // legacy
  | { type: "assistant_tool_call_start"; tool_name: string; input?: unknown }
  | { type: "assistant_tool_call_end"; tool_name: string; output?: unknown }
  | { type: "subagent_tool_call_start"; tool_name: string; input?: unknown }
  | { type: "subagent_tool_call_end"; tool_name: string; output?: unknown }
  | { type: "end" }
  | { type: "error"; message: string };

export type TimelineItem =
  | { kind: 'assistant'; assistantName: string; blocks: { content: string; isComplete: boolean }[] }
  | { kind: 'tool_call'; toolName: string; state: "loading" | "ready" | "error" | "default"; input?: unknown; output?: unknown };
