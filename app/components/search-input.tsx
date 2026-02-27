"use client";

import { useState, useRef, forwardRef, useImperativeHandle, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

import { Input } from "@/components/ui/input";
import { Mode, MODES, SSEEvent, StreamEventItem } from "@/app/types";
import { Loader2 } from "lucide-react";

interface SearchInputProps {
  initialSearch?: string;
  mode: Mode;
  onResponseReceived?: (response: string) => void;
  onThinkingTokenReceived?: (assistantName: string, token: string) => void;
  onThinkingComplete?: (assistantName: string) => void;
  onToolCallStart?: (toolName: string, input?: unknown) => void;
  onToolCallEnd?: (toolName: string, output?: unknown) => void;
  onSubagentTokenReceived?: (assistantName: string, token: string) => void;
  onSubagentToolCallStart?: (parentToolName: string, toolName: string, input?: unknown) => void;
  onSubagentToolCallEnd?: (parentToolName: string, toolName: string, output?: unknown) => void;
  onStreamEvent?: (event: StreamEventItem) => void;
  onStreamingStateChange?: (isStreaming: boolean) => void;
}

export interface SearchInputHandle {
  focus: () => void;
}

const SearchInput = forwardRef<SearchInputHandle, SearchInputProps>(
  ({
    initialSearch = "",
    mode,
    onResponseReceived,
    onThinkingTokenReceived,
    onThinkingComplete,
    onToolCallStart,
    onToolCallEnd,
    onSubagentTokenReceived,
    onSubagentToolCallStart,
    onSubagentToolCallEnd,
    onStreamEvent,
    onStreamingStateChange,
  }, ref) => {
    const [search, setSearch] = useState(initialSearch);
    const router = useRouter();
    const inputRef = useRef<HTMLInputElement>(null);
    const prevModeRef = useRef(mode);
    const [isLoading, setIsLoading] = useState(false);
    const frameRequestRef = useRef<number | null>(null);
    const currentResponseRef = useRef<string>('');

    const cancelScheduledResponse = useCallback(() => {
      if (frameRequestRef.current === null) {
        return;
      }

      if (typeof window !== "undefined") {
        window.cancelAnimationFrame(frameRequestRef.current);
      }

      frameRequestRef.current = null;
    }, []);

    const flushPendingResponse = useCallback(() => {
      cancelScheduledResponse();
      onResponseReceived?.(currentResponseRef.current);
    }, [cancelScheduledResponse, onResponseReceived]);

    useImperativeHandle(ref, () => ({
      focus: () => {
        inputRef.current?.focus();
      }
    }));

    useEffect(() => {
      if (prevModeRef.current !== mode) {
        setSearch("");
        onResponseReceived?.("");
        router.push("/");
        prevModeRef.current = mode;
      }
    }, [mode, onResponseReceived, router]);

    const scheduleResponseUpdate = useCallback((response: string) => {
      currentResponseRef.current = response;

      if (frameRequestRef.current !== null) {
        return;
      }

      if (typeof window === "undefined") {
        flushPendingResponse();
        return;
      }

      frameRequestRef.current = window.requestAnimationFrame(flushPendingResponse);
    }, [flushPendingResponse]);

    useEffect(() => {
      return () => {
        cancelScheduledResponse();
      };
    }, [cancelScheduledResponse]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setSearch(value);
      if (mode === MODES.SEARCH) {
        router.push(`/?search=${encodeURIComponent(value)}`);
      }
    };

    const handleSubmit = async (value: string) => {
      if (mode !== MODES.AGENT) {
        return;
      }
      try {
        setIsLoading(true);
        onStreamingStateChange?.(true);
        currentResponseRef.current = '';
        onResponseReceived?.('');
        
        const response = await fetch('/api/agent/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: value }),
        });
        
        if (!response.ok) throw new Error('Failed to stream agent response');
        
        const reader = response.body?.getReader();
        if (!reader) throw new Error('Response body is null');
        
        const decoder = new TextDecoder();
        let accumulatedResponse = '';
        let buffer = '';
        let eventSequence = 0;

        const getEventLabel = (eventData: SSEEvent): string => {
          switch (eventData.type) {
            case "assistant_token":
              return "Assistant";
            case "thinking_token":
              return "Assistant Thinking";
            case "subagent_thinking_token":
              return `Thinking • ${eventData.tool_name}`;
            case "subagent_token":
              return `Subagent • ${eventData.tool_name}`;
            case "assistant_tool_call_start":
            case "assistant_tool_call_end":
            case "subagent_tool_call_start":
            case "subagent_tool_call_end":
              return `Tool Call • ${eventData.tool_name}`;
            default:
              return "System";
          }
        };

        const parseSsePayloads = (
          currentBuffer: string,
          flushRemainder: boolean = false
        ): { nextBuffer: string; payloads: string[] } => {
          const normalized = currentBuffer.replace(/\r\n/g, "\n");
          const frames = normalized.split("\n\n");
          const payloads: string[] = [];
          const completeFrames = flushRemainder ? frames : frames.slice(0, -1);
          const nextBuffer = flushRemainder ? "" : (frames[frames.length - 1] || "");

          for (const frame of completeFrames) {
            if (!frame.trim()) {
              continue;
            }
            const dataLines = frame
              .split("\n")
              .map((line) => line.trimEnd())
              .filter((line) => line.startsWith("data:"))
              .map((line) => line.slice(5).trimStart())
              .filter(Boolean);
            if (dataLines.length > 0) {
              payloads.push(dataLines.join("\n"));
            }
          }

          return { nextBuffer, payloads };
        };

        const publishStreamEvent = (
          eventData: SSEEvent,
          token: string,
          label: string,
          metadata?: Partial<Pick<StreamEventItem, "kind" | "toolName" | "toolCallId" | "parentToolName" | "payload">>
        ) => {
          if (!token && !metadata?.kind) {
            return;
          }
          eventSequence += 1;
          onStreamEvent?.({
            id: `stream-event-${Date.now()}-${eventSequence}`,
            source: eventData.source,
            label,
            token,
            timestamp: Date.now(),
            kind: metadata?.kind ?? "default",
            toolName: metadata?.toolName,
            toolCallId: metadata?.toolCallId,
            parentToolName: metadata?.parentToolName,
            payload: metadata?.payload,
          });
        };

        const publishToolLifecycleEvent = (
          eventData:
            | Extract<SSEEvent, { type: "assistant_tool_call_start" }>
            | Extract<SSEEvent, { type: "assistant_tool_call_end" }>
            | Extract<SSEEvent, { type: "subagent_tool_call_start" }>
            | Extract<SSEEvent, { type: "subagent_tool_call_end" }>,
          kind: "tool_call_request" | "tool_call_response",
          payload: unknown
        ) => {
          const parentToolName =
            "parent_tool_name" in eventData ? eventData.parent_tool_name : undefined;
          publishStreamEvent(eventData, "", getEventLabel(eventData), {
            kind,
            toolName: eventData.tool_name,
            toolCallId: eventData.call_id,
            parentToolName,
            payload,
          });
        };

        const dispatchEvent = (eventData: SSEEvent): "continue" | "end" => {
          switch (eventData.type) {
            case 'assistant_token': {
              accumulatedResponse += eventData.token;
              scheduleResponseUpdate(accumulatedResponse);
              publishStreamEvent(eventData, eventData.token, getEventLabel(eventData));
              return "continue";
            }
            case 'thinking_token': {
              onThinkingTokenReceived?.("Assistant", eventData.token);
              publishStreamEvent(eventData, eventData.token, getEventLabel(eventData));
              return "continue";
            }
            case 'thinking_complete': {
              onThinkingComplete?.("Assistant");
              return "continue";
            }
            case 'subagent_thinking_token': {
              onThinkingTokenReceived?.(eventData.tool_name, eventData.token);
              publishStreamEvent(eventData, eventData.token, getEventLabel(eventData));
              return "continue";
            }
            case 'subagent_thinking_complete': {
              onThinkingComplete?.(eventData.tool_name);
              return "continue";
            }
            case 'subagent_token': {
              onSubagentTokenReceived?.(eventData.tool_name, eventData.token);
              publishStreamEvent(eventData, eventData.token, getEventLabel(eventData));
              return "continue";
            }
            case 'assistant_tool_call_start':
            case 'subagent_tool_call_start':
              if (eventData.type === 'subagent_tool_call_start') {
                onSubagentToolCallStart?.(
                  eventData.parent_tool_name,
                  eventData.tool_name,
                  eventData.input
                );
              } else {
                onToolCallStart?.(eventData.tool_name, eventData.input);
              }
              publishToolLifecycleEvent(eventData, "tool_call_request", eventData.input);
              return "continue";
            case 'assistant_tool_call_end':
            case 'subagent_tool_call_end':
              if (eventData.type === 'subagent_tool_call_end') {
                onSubagentToolCallEnd?.(
                  eventData.parent_tool_name,
                  eventData.tool_name,
                  eventData.output
                );
              } else {
                onToolCallEnd?.(eventData.tool_name, eventData.output);
              }
              publishToolLifecycleEvent(eventData, "tool_call_response", eventData.output);
              return "continue";
            case 'end': {
              setIsLoading(false);
              onStreamingStateChange?.(false);
              flushPendingResponse();
              return "end";
            }
            case 'error': {
              publishStreamEvent(eventData, eventData.message, getEventLabel(eventData));
              flushPendingResponse();
              setIsLoading(false);
              onStreamingStateChange?.(false);
              return "end";
            }
            default:
              return "continue";
          }
        };

        const processCompletedEvent = (eventPayload: string): "continue" | "end" => {
          try {
            const eventData: SSEEvent = JSON.parse(eventPayload);
            return dispatchEvent(eventData);
          } catch (parseError) {
            console.warn('Failed to parse SSE event:', eventPayload, parseError);
            return "continue";
          }
        };

        while (true) {
          const { done, value } = await reader.read();

          if (value) {
            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;
          }

          const parsed = parseSsePayloads(buffer);
          buffer = parsed.nextBuffer;

          for (const eventPayload of parsed.payloads) {
            const status = processCompletedEvent(eventPayload);
            if (status === "end") {
              return;
            }
          }

          if (done) {
            const flushed = parseSsePayloads(buffer, true);
            buffer = flushed.nextBuffer;
            for (const eventPayload of flushed.payloads) {
              const status = processCompletedEvent(eventPayload);
              if (status === "end") {
                break;
              }
            }
            break;
          }
        }
      } catch (error) {
        console.error('Failed to stream agent response:', error);
        onResponseReceived?.('Error: Failed to retrieve response');
      } finally {
        onStreamingStateChange?.(false);
        cancelScheduledResponse();
        setIsLoading(false);
      }
    };

    const handleKeyDown = async (e: React.KeyboardEvent<HTMLInputElement>) => {
      const value = e.currentTarget.value;
      
      if (e.key === 'Escape') {
        setSearch('');
        if (mode === MODES.SEARCH) {
          router.push('/');
        }
        return;
      }
      
      if (mode === MODES.AGENT && e.key === 'Enter') {
        e.preventDefault();
        await handleSubmit(value);
      }
    };

    return (
      <>
        {isLoading ? (
          <div className="flex justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <form 
            className="flex gap-2 relative"
            onSubmit={async (e) => {
              e.preventDefault();
              await handleSubmit(search);
            }}
          >
            <Input
              ref={inputRef}
              type={mode === MODES.SEARCH ? "search" : "text"}
              name={mode}
              autoComplete="off"
              placeholder={mode === MODES.SEARCH ? "Search memories..." : "Delve into your memories..."}
              value={search}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              className="flex-grow"
            />
          </form>
        )}
      </>
    );
  }
);

SearchInput.displayName = "SearchInput";
export { SearchInput };
