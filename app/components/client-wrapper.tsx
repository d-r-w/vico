"use client";

import { useState, useRef } from "react";
import { MODES, Mode, ThinkingBlock, StreamEventItem, SubagentState, ToolCallState } from "@/app/types";
import { ResponseDisplay } from "@/app/components/response-display";
import { SearchHeader } from "@/app/components/search-header";

interface ClientWrapperProps {
  initialSearch: string;
  onToggleSidebar?: () => void;
}

export function ClientWrapper({ initialSearch, onToggleSidebar }: ClientWrapperProps) {
  const [response, setResponse] = useState<string>("");
  const [mode, setMode] = useState<Mode>(MODES.AGENT);
  const [assistantThinking, setAssistantThinking] = useState<ThinkingBlock[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCallState[]>([]);
  const [streamEvents, setStreamEvents] = useState<StreamEventItem[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const toolCallIdRef = useRef(0);

  const findLastIndex = <T,>(arr: T[], predicate: (value: T, index: number) => boolean) => {
    for (let i = arr.length - 1; i >= 0; i -= 1) {
      if (predicate(arr[i], i)) {
        return i;
      }
    }
    return -1;
  };

  const nextToolCallId = () => {
    toolCallIdRef.current += 1;
    return `tool-call-${toolCallIdRef.current}`;
  };

  const resetConversationState = () => {
    setAssistantThinking([]);
    setToolCalls([]);
    setStreamEvents([]);
    setIsStreaming(false);
  };

  const appendThinkingToken = (blocks: ThinkingBlock[], token: string): ThinkingBlock[] => {
    if (!token) {
      return blocks;
    }
    if (blocks.length === 0) {
      return [{ content: token, isComplete: false }];
    }
    const lastBlock = blocks[blocks.length - 1];
    if (lastBlock.isComplete) {
      return [...blocks, { content: token, isComplete: false }];
    }
    const next = [...blocks];
    next[next.length - 1] = { ...lastBlock, content: lastBlock.content + token };
    return next;
  };

  const completeThinkingBlock = (blocks: ThinkingBlock[]): ThinkingBlock[] => {
    if (blocks.length === 0) {
      return blocks;
    }
    const next = [...blocks];
    const lastIndex = next.length - 1;
    const last = next[lastIndex];
    if (last.isComplete) {
      return next;
    }
    next[lastIndex] = { ...last, isComplete: true };
    return next;
  };

  const ensureSubagent = (call: ToolCallState): SubagentState => {
    if (call.subagent) {
      return {
        ...call.subagent,
        thinkingBlocks: [...call.subagent.thinkingBlocks],
        toolCalls: [...call.subagent.toolCalls],
      };
    }
    return {
      name: call.toolName,
      chat: "",
      thinkingBlocks: [],
      toolCalls: [],
    };
  };

  const updateToolCall = (toolName: string, updater: (call: ToolCallState) => ToolCallState) => {
    setToolCalls(prev => {
      const index = findLastIndex(prev, tc => tc.toolName === toolName);
      if (index === -1) {
        return prev;
      }
      const current = prev[index];
      const updated = updater(current);
      if (updated === current) {
        return prev;
      }
      const next = [...prev];
      next[index] = updated;
      return next;
    });
  };

  const updateNestedToolCall = (
    parentToolName: string,
    toolName: string,
    updater: (call: ToolCallState) => ToolCallState,
  ) => {
    setToolCalls(prev => {
      const parentIndex = findLastIndex(prev, tc => tc.toolName === parentToolName);
      if (parentIndex === -1) {
        return prev;
      }
      const parent = prev[parentIndex];
      if (!parent.subagent) {
        return prev;
      }
      const nestedCalls = [...parent.subagent.toolCalls];
      const nestedIndex = findLastIndex(nestedCalls, tc => tc.toolName === toolName);
      if (nestedIndex === -1) {
        return prev;
      }
      const updatedNested = updater(nestedCalls[nestedIndex]);
      if (updatedNested === nestedCalls[nestedIndex]) {
        return prev;
      }
      nestedCalls[nestedIndex] = updatedNested;
      const next = [...prev];
      next[parentIndex] = {
        ...parent,
        subagent: {
          ...parent.subagent,
          toolCalls: nestedCalls,
        },
      };
      return next;
    });
  };

  const handleToolCallStart = (toolName: string, input?: unknown) => {
    const id = nextToolCallId();
    setToolCalls(prev => [...prev, { id, toolName, state: "loading", input }]);
  };

  const handleToolCallEnd = (toolName: string, output?: unknown) => {
    updateToolCall(toolName, call => ({
      ...call,
      state: "ready",
      output,
    }));
  };

  const handleThinkingToken = (assistantName: string, token: string) => {
    if (!token) {
      return;
    }
    if (assistantName === "Assistant") {
      setAssistantThinking(prev => appendThinkingToken(prev, token));
      return;
    }
    updateToolCall(assistantName, call => {
      const subagent = ensureSubagent(call);
      const nextSubagent: SubagentState = {
        ...subagent,
        thinkingBlocks: appendThinkingToken(subagent.thinkingBlocks, token),
      };
      return {
        ...call,
        state: "loading",
        subagent: nextSubagent,
      };
    });
  };

  const handleThinkingComplete = (assistantName: string) => {
    if (assistantName === "Assistant") {
      setAssistantThinking(prev => completeThinkingBlock(prev));
      return;
    }
    updateToolCall(assistantName, call => {
      const subagent = call.subagent;
      if (!subagent || subagent.thinkingBlocks.length === 0) {
        return call;
      }
      return {
        ...call,
        subagent: {
          ...subagent,
          thinkingBlocks: completeThinkingBlock(subagent.thinkingBlocks),
        },
      };
    });
  };

  const handleSubagentToken = (toolName: string, token: string) => {
    if (!token) {
      return;
    }
    updateToolCall(toolName, call => {
      const subagent = ensureSubagent(call);
      return {
        ...call,
        state: "loading",
        subagent: {
          ...subagent,
          chat: subagent.chat + token,
        },
      };
    });
  };

  const handleSubagentToolCallStart = (parentToolName: string, toolName: string, input?: unknown) => {
    const id = nextToolCallId();
    setToolCalls(prev => {
      const index = findLastIndex(prev, tc => tc.toolName === parentToolName);
      if (index === -1) {
        return prev;
      }
      const current = prev[index];
      const subagent = ensureSubagent(current);
      const updatedParent: ToolCallState = {
        ...current,
        subagent: {
          ...subagent,
          toolCalls: [...subagent.toolCalls, { id, toolName, state: "loading", input }],
        },
      };
      const next = [...prev];
      next[index] = updatedParent;
      return next;
    });
  };

  const handleSubagentToolCallEnd = (parentToolName: string, toolName: string, output?: unknown) => {
    updateNestedToolCall(parentToolName, toolName, call => ({
      ...call,
      state: "ready",
      output,
    }));
  };

  const handleResponseReceived = (value: string) => {
    setResponse(value);
    if (value === "") {
      resetConversationState();
    }
  };

  const handleStreamEvent = (event: StreamEventItem) => {
    setStreamEvents(prev => [...prev, event]);
  };

  const handleStreamingStateChange = (value: boolean) => {
    setIsStreaming(value);
  };

  return (
    <div className="flex flex-col h-full">
      <SearchHeader 
        initialSearch={initialSearch}
        mode={mode}
        onModeChange={setMode}
        onResponseReceived={handleResponseReceived}
        onThinkingTokenReceived={handleThinkingToken}
        onThinkingComplete={handleThinkingComplete}
        onToolCallStart={handleToolCallStart}
        onToolCallEnd={handleToolCallEnd}
        onSubagentTokenReceived={handleSubagentToken}
        onSubagentToolCallStart={handleSubagentToolCallStart}
        onSubagentToolCallEnd={handleSubagentToolCallEnd}
        onStreamEvent={handleStreamEvent}
        onStreamingStateChange={handleStreamingStateChange}
        onToggleSidebar={onToggleSidebar}
      />
      <div className="container mx-auto px-3 flex-1 flex flex-col h-[calc(100%-3.5rem)] pb-3">
        {response || assistantThinking.length > 0 || toolCalls.length > 0 || streamEvents.length > 0 || isStreaming ? (
          <div className="h-full flex-1">
            <ResponseDisplay 
              content={response} 
              streamEvents={streamEvents}
              isStreaming={isStreaming}
            />
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <p>Enter a prompt above to get started</p>
          </div>
        )}
      </div>
    </div>
  );
} 
