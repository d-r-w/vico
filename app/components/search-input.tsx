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
        setSearch('');
        router.push('/');
        prevModeRef.current = mode;
      }
    }, [mode, router]);

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
      if (mode === MODES.CHAT || mode === MODES.AGENT) {
        try {
          setIsLoading(true);
          onStreamingStateChange?.(true);
          currentResponseRef.current = '';
          onResponseReceived?.('');
          
          const response = await fetch('/api/memories/probe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              query: value,
              isAgent: mode === MODES.AGENT
            }),
          });
          
          if (!response.ok) throw new Error('Failed to probe memories');
          
          const reader = response.body?.getReader();
          if (!reader) throw new Error('Response body is null');
          
          const decoder = new TextDecoder();
          let accumulatedResponse = '';
          let buffer = '';
          let eventBuffer: string[] = [];
          let eventSequence = 0;

          const publishStreamEvent = (eventData: SSEEvent, token: string, label: string) => {
            if (!token) {
              return;
            }
            eventSequence += 1;
            onStreamEvent?.({
              id: `stream-event-${Date.now()}-${eventSequence}`,
              source: eventData.source,
              label,
              token,
              timestamp: Date.now(),
            });
          };

          const dispatchEvent = (eventData: SSEEvent): "continue" | "end" => {
            switch (eventData.type) {
              case 'assistant_token': {
                accumulatedResponse += eventData.token;
                scheduleResponseUpdate(accumulatedResponse);
                publishStreamEvent(eventData, eventData.token, "Assistant");
                return "continue";
              }
              case 'thinking_token': {
                onThinkingTokenReceived?.("Assistant", eventData.token);
                publishStreamEvent(eventData, eventData.token, "Assistant Thinking");
                return "continue";
              }
              case 'thinking_complete': {
                onThinkingComplete?.("Assistant");
                return "continue";
              }
              case 'subagent_thinking_token': {
                onThinkingTokenReceived?.(eventData.tool_name, eventData.token);
                publishStreamEvent(eventData, eventData.token, `Thinking • ${eventData.tool_name}`);
                return "continue";
              }
              case 'subagent_thinking_complete': {
                onThinkingComplete?.(eventData.tool_name);
                return "continue";
              }
              case 'subagent_token': {
                onSubagentTokenReceived?.(eventData.tool_name, eventData.token);
                publishStreamEvent(eventData, eventData.token, `Subagent • ${eventData.tool_name}`);
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
                return "continue";
              case 'assistant_tool_call_end':
              case 'subagent_tool_call_end':
                if (eventData.type === 'subagent_tool_call_end') {
                  onSubagentToolCallEnd?.(
                    eventData.parent_tool_name,
                    eventData.tool_name,
                    eventData.output
                  );
                  if (typeof eventData.output === "string" && eventData.output.trim().length > 0) {
                    publishStreamEvent(
                      eventData,
                      eventData.output,
                      `Tool Result • ${eventData.tool_name}`
                    );
                  }
                } else {
                  onToolCallEnd?.(eventData.tool_name, eventData.output);
                  if (typeof eventData.output === "string" && eventData.output.trim().length > 0) {
                    publishStreamEvent(eventData, eventData.output, `Tool Result • ${eventData.tool_name}`);
                  }
                }
                return "continue";
              case 'end': {
                setIsLoading(false);
                onStreamingStateChange?.(false);
                flushPendingResponse();
                return "end";
              }
              case 'error': {
                throw new Error(eventData.message);
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

            // Parse SSE events from buffer
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer

            for (const rawLine of lines) {
              const line = rawLine.replace(/\r$/, '');

              if (line.startsWith('data:')) {
                const jsonChunk = line.slice(5).trimStart();
                if (jsonChunk) {
                  eventBuffer.push(jsonChunk);
                }
                continue;
              }

              // Blank line marks end of SSE event
              if (line === '') {
                if (eventBuffer.length === 0) continue;
                const eventPayload = eventBuffer.join('\n');
                eventBuffer = [];
                const status = processCompletedEvent(eventPayload);
                if (status === "end") {
                  return;
                }
              }
            }

            if (done) {
              const trailingLine = buffer.replace(/\r$/, '');
              if (trailingLine.startsWith('data:')) {
                const jsonChunk = trailingLine.slice(5).trimStart();
                if (jsonChunk) {
                  eventBuffer.push(jsonChunk);
                }
              }

              // Flush any buffered event in case the stream ended without a trailing blank line
              if (eventBuffer.length > 0) {
                const eventPayload = eventBuffer.join('\n');
                eventBuffer = [];
                const status = processCompletedEvent(eventPayload);
                if (status === "end") {
                  break;
                }
              }
              break;
            }
          }
        } catch (error) {
          console.error('Failed to probe memories:', error);
          onResponseReceived?.('Error: Failed to retrieve response');
        } finally {
          onStreamingStateChange?.(false);
          cancelScheduledResponse();
          setIsLoading(false);
        }
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
      
      if ((mode === MODES.CHAT || mode === MODES.AGENT) && e.key === 'Enter') {
        e.preventDefault();
        await handleSubmit(value);
      }
    };

    const getPlaceholder = () => {
      switch (mode) {
        case MODES.SEARCH:
          return "Search memories...";
        case MODES.CHAT:
          return "Ask about your memories...";
        case MODES.AGENT:
          return "Delve into your memories...";
        default:
          return "Search memories...";
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
              placeholder={getPlaceholder()}
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
