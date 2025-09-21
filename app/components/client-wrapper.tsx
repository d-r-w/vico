"use client";

import { useState, useEffect, useRef } from "react";
import { MODES, Mode, AssistantThinking, TimelineItem } from "@/app/types";
import { ResponseDisplay } from "@/app/components/response-display";
import { SearchHeader } from "@/app/components/search-header";
import { SearchInputHandle } from "@/app/components/search-input";

interface ToolCall {
  toolName: string;
  state: "loading" | "ready" | "error" | "default";
  input?: unknown;
  output?: unknown;
}

interface ClientWrapperProps {
  initialSearch: string;
}

export function ClientWrapper({ initialSearch }: ClientWrapperProps) {
  const [response, setResponse] = useState<string>("");
  const [mode, setMode] = useState<Mode>(MODES.SEARCH);
  const [assistantThinking, setAssistantThinking] = useState<AssistantThinking>({});
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const searchInputRef = useRef<SearchInputHandle>(null);
  
  useEffect(() => {
    searchInputRef.current?.focus();
  }, []);

  const findLastIndex = <T,>(arr: T[], predicate: (value: T, index: number) => boolean) => {
    for (let i = arr.length - 1; i >= 0; i -= 1) {
      if (predicate(arr[i], i)) {
        return i;
      }
    }
    return -1;
  };

  const handleToolCallStart = (toolName: string, input?: unknown) => {
    setToolCalls(prev => [...prev, { toolName, state: "loading", input }]);
    setTimeline(prev => [...prev, { kind: 'tool_call', toolName, state: "loading", input }]);
  };

  const handleToolCallEnd = (toolName: string, output?: unknown) => {
    setToolCalls(prev => {
      if (prev.length === 0) return prev;
      const index = findLastIndex(prev, tc => tc.toolName === toolName);
      if (index === -1) return prev;
      const next = [...prev];
      next[index] = { ...next[index], state: "ready", output };
      return next;
    });

    setTimeline(prev => {
      if (prev.length === 0) return prev;
      const index = findLastIndex(prev, item => item.kind === 'tool_call' && item.toolName === toolName);
      if (index === -1) return prev;
      const next = [...prev];
      const item = next[index];
      if (item.kind !== 'tool_call') return prev;
      next[index] = { ...item, state: "ready", output };
      return next;
    });
  };

  const handleThinkingToken = (assistantName: string, token: string) => {
    setAssistantThinking(prev => {
      const currentBlocks = prev[assistantName] || [];
      const lastBlock = currentBlocks[currentBlocks.length - 1];
      
      if (lastBlock && !lastBlock.isComplete) {
        // Append to the last incomplete thinking block
        const updatedBlocks = [...currentBlocks];
        updatedBlocks[updatedBlocks.length - 1] = {
          ...lastBlock,
          content: lastBlock.content + token
        };
        return {
          ...prev,
          [assistantName]: updatedBlocks
        };
      } else {
        // Create a new thinking block
        return {
          ...prev,
          [assistantName]: [...currentBlocks, { content: token, isComplete: false }]
        };
      }
    });

    // Update tool call state to show it's active if it's a subagent
    if (assistantName !== "Assistant") {
      setToolCalls(prev => {
        if (prev.length === 0) return prev;
        const index = findLastIndex(prev, tc => tc.toolName === assistantName);
        if (index === -1) return prev;
        return prev.map((tc, idx) => idx === index ? { ...tc, state: "loading" as const } : tc);
      });
    }

    // Ensure timeline has an assistant entry to append to chronologically
    setTimeline(prev => {
      const last = prev[prev.length - 1];
      if (!last || last.kind !== 'assistant' || last.assistantName !== assistantName) {
        return [...prev, { kind: 'assistant', assistantName, blocks: [{ content: token, isComplete: false }] }];
      }
      const rest = prev.slice(0, -1);
      const lastAssistant = last as Extract<TimelineItem, { kind: 'assistant' }>;
      const blocks = lastAssistant.blocks;
      const lastBlock = blocks[blocks.length - 1];
      const nextBlocks = lastBlock && !lastBlock.isComplete
        ? [...blocks.slice(0, -1), { ...lastBlock, content: lastBlock.content + token }]
        : [...blocks, { content: token, isComplete: false }];
      return [...rest, { ...lastAssistant, blocks: nextBlocks }];
    });
  };

  const handleThinkingComplete = (assistantName: string) => {
    setAssistantThinking(prev => {
      const currentBlocks = prev[assistantName] || [];
      if (currentBlocks.length === 0) return prev;
      
      const updatedBlocks = [...currentBlocks];
      const lastIndex = updatedBlocks.length - 1;
      updatedBlocks[lastIndex] = {
        ...updatedBlocks[lastIndex],
        isComplete: true
      };
      
      return {
        ...prev,
        [assistantName]: updatedBlocks
      };
    });

    setTimeline(prev => {
      const last = prev[prev.length - 1];
      if (!last || last.kind !== 'assistant' || last.assistantName !== assistantName) {
        return prev;
      }
      const rest = prev.slice(0, -1);
      const blocks = last.blocks;
      if (blocks.length === 0) {
        return prev;
      }
      const nextBlocks = [...blocks.slice(0, -1), { ...blocks[blocks.length - 1], isComplete: true }];
      return [...rest, { ...last, blocks: nextBlocks }];
    });
  };

  const handleResponseReceived = (response: string) => {
    setResponse(response);
    // Clear assistant thinking when we get a new response
    if (response === '') {
      setAssistantThinking({});
      setToolCalls([]);
      setTimeline([]);
    }
  };

  // Global SSE hookup to enrich timeline with tool start/end, if caller chooses to forward raw events here later
  // Placeholder to show how to handle such events centrally if needed in future


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
      />
      <div className="container mx-auto px-3 flex-1 flex flex-col h-[calc(100%-3.5rem)] pb-3">
        {response || Object.keys(assistantThinking).length > 0 || toolCalls.length > 0 ? (
          <div className="h-full flex-1">
            <ResponseDisplay 
              content={response} 
              assistantThinking={assistantThinking}
              toolCalls={toolCalls}
              timeline={timeline}
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
