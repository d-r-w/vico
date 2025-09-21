"use client";

import { useState, useRef, forwardRef, useImperativeHandle, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

import { Input } from "@/components/ui/input";
import { Mode, MODES, SSEEvent } from "@/app/types";
import { Loader2 } from "lucide-react";

interface SearchInputProps {
  initialSearch?: string;
  mode: Mode;
  onResponseReceived?: (response: string) => void;
  onThinkingTokenReceived?: (assistantName: string, token: string) => void;
  onThinkingComplete?: (assistantName: string) => void;
  onToolCallStart?: (toolName: string, input?: unknown) => void;
  onToolCallEnd?: (toolName: string, output?: unknown) => void;
}

export interface SearchInputHandle {
  focus: () => void;
}

const SearchInput = forwardRef<SearchInputHandle, SearchInputProps>(
  ({ initialSearch = "", mode, onResponseReceived, onThinkingTokenReceived, onThinkingComplete, onToolCallStart, onToolCallEnd }, ref) => {
    const [search, setSearch] = useState(initialSearch);
    const router = useRouter();
    const inputRef = useRef<HTMLInputElement>(null);
    const prevModeRef = useRef(mode);
    const [isLoading, setIsLoading] = useState(false);
    const responseUpdateTimerRef = useRef<NodeJS.Timeout | null>(null);
    const currentResponseRef = useRef<string>('');

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

    const throttledResponseUpdate = useCallback((response: string) => {
      currentResponseRef.current = response;
      
      if (responseUpdateTimerRef.current) {
        clearTimeout(responseUpdateTimerRef.current);
      }
      
      responseUpdateTimerRef.current = setTimeout(() => {
        onResponseReceived?.(currentResponseRef.current);
      }, 16); // ~60fps for smooth updates
    }, [onResponseReceived]);

    useEffect(() => {
      return () => {
        if (responseUpdateTimerRef.current) {
          clearTimeout(responseUpdateTimerRef.current);
        }
      };
    }, []);

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

                try {
                  const eventData: SSEEvent = JSON.parse(eventPayload);

                  switch (eventData.type) {
                    case 'assistant_token': {
                      accumulatedResponse += eventData.token;
                      throttledResponseUpdate(accumulatedResponse);
                      break;
                    }
                    case 'thinking_token': {
                      onThinkingTokenReceived?.("Assistant", eventData.token);
                      break;
                    }
                    case 'thinking_complete': {
                      onThinkingComplete?.("Assistant");
                      break;
                    }
                    case 'subagent_thinking_token': {
                      onThinkingTokenReceived?.(eventData.tool_name, eventData.token);
                      break;
                    }
                    case 'subagent_thinking_complete': {
                      onThinkingComplete?.(eventData.tool_name);
                      break;
                    }
                    case 'subagent_token': {
                      // Non-reasoning subagent narration is surfaced via tool call UI.
                      break;
                    }
                    case 'assistant_tool_call_start':
                    case 'subagent_tool_call_start':
                    case 'tool_call_start': // legacy
                      onToolCallStart?.(eventData.tool_name, eventData.input);
                      break;
                    case 'assistant_tool_call_end':
                    case 'subagent_tool_call_end':
                    case 'tool_call_end': // legacy
                      onToolCallEnd?.(eventData.tool_name, eventData.output);
                      break;
                    case 'end': {
                      setIsLoading(false);
                      if (responseUpdateTimerRef.current) {
                        clearTimeout(responseUpdateTimerRef.current);
                        onResponseReceived?.(currentResponseRef.current);
                      }
                      return;
                    }
                    case 'error': {
                      throw new Error(eventData.message);
                    }
                    default:
                      break;
                  }
                } catch (parseError) {
                  console.warn('Failed to parse SSE event:', eventPayload, parseError);
                }
              }
            }

            if (done) {
              // Flush any buffered event in case the stream ended without a trailing blank line
              if (eventBuffer.length > 0) {
                const eventPayload = eventBuffer.join('\n');
                eventBuffer = [];
                try {
                  const eventData: SSEEvent = JSON.parse(eventPayload);
                  switch (eventData.type) {
                    case 'assistant_token':
                      accumulatedResponse += eventData.token;
                      throttledResponseUpdate(accumulatedResponse);
                      break;
                    case 'thinking_token':
                      onThinkingTokenReceived?.("Assistant", eventData.token);
                      break;
                    case 'thinking_complete':
                      onThinkingComplete?.("Assistant");
                      break;
                    case 'subagent_thinking_token':
                      onThinkingTokenReceived?.(eventData.tool_name, eventData.token);
                      break;
                    case 'subagent_thinking_complete':
                      onThinkingComplete?.(eventData.tool_name);
                      break;
                    case 'subagent_token':
                      // Non-reasoning subagent narration is surfaced via tool call UI.
                      break;
                    case 'tool_call_start':
                      onToolCallStart?.(eventData.tool_name, eventData.input);
                      break;
                    case 'tool_call_end':
                      onToolCallEnd?.(eventData.tool_name, eventData.output);
                      break;
                    case 'end':
                      setIsLoading(false);
                      if (responseUpdateTimerRef.current) {
                        clearTimeout(responseUpdateTimerRef.current);
                        onResponseReceived?.(currentResponseRef.current);
                      }
                      break;
                    case 'error':
                      throw new Error(eventData.message);
                    default:
                      break;
                  }
                } catch (parseError) {
                  console.warn('Failed to parse trailing SSE event:', eventPayload, parseError);
                }
              }
              break;
            }
          }
        } catch (error) {
          console.error('Failed to probe memories:', error);
          onResponseReceived?.('Error: Failed to retrieve response');
        } finally {
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
