"use client"

import { memo, useMemo } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { MarkdownRenderer } from "@/app/components/markdown-renderer"
import { useAutoScroll } from "@/app/hooks/useAutoScroll"
import type { StreamEventItem, StreamSource } from "@/app/types"

interface ResponseDisplayProps {
  content: string;
  streamEvents: StreamEventItem[];
  isStreaming: boolean;
}

const StreamingBadge = ({ isStreaming }: { isStreaming: boolean }) => (
  <span
    className={`inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide ${
      isStreaming ? "text-amber-600" : "text-emerald-600"
    }`}
  >
    <span
      className={`w-1.5 h-1.5 rounded-full ${
        isStreaming ? "bg-amber-500 animate-pulse" : "bg-emerald-500"
      }`}
    />
    {isStreaming ? "streaming" : "complete"}
  </span>
);

const TOOL_REQUEST_BADGE_CLASS =
  "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-100";
const TOOL_RESULT_BADGE_CLASS =
  "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-100";
const DISCLOSURE_HINT_CLASS = "text-[11px] font-medium uppercase tracking-wide text-zinc-400";

const sourceTone: Record<StreamSource, { badge: string; label: string }> = {
  assistant: {
    badge: "border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-800 dark:bg-sky-900/30 dark:text-sky-100",
    label: "Assistant",
  },
  assistant_thinking: {
    badge: "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-100",
    label: "Thinking",
  },
  subagent: {
    badge: "border-zinc-400 bg-zinc-200 text-zinc-700 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-200",
    label: "Subagent",
  },
  subagent_thinking: {
    badge: "border-zinc-400 bg-zinc-200 text-zinc-700 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-200",
    label: "Subagent Thinking",
  },
  assistant_tool: {
    badge: TOOL_RESULT_BADGE_CLASS,
    label: "Tool",
  },
  subagent_tool: {
    badge: TOOL_RESULT_BADGE_CLASS,
    label: "Tool",
  },
  system: {
    badge: "border-zinc-400 bg-zinc-200 text-zinc-700 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-200",
    label: "System",
  },
};

const TOOL_CALL_BLOCK_REGEX = /<tool_call>[\s\S]*?<\/tool_call>/gi;
const TOOL_NAME_REGEX = /<function\s*=\s*("?)([^">\s]+)\1\s*>/i;
const PARAM_REGEX = /<parameter\s*=\s*("?)([^">\s]+)\1\s*>([\s\S]*?)<\/parameter(?:\s*=\s*("?)([^">\s]+)\4\s*)?\s*>/gi;

const extractToolCallBlocks = (text: string): string[] => {
  const blocks = text.match(TOOL_CALL_BLOCK_REGEX);
  if (!blocks) {
    return [];
  }
  return blocks;
};

const isToolResultLabel = (label: string) => label.toLowerCase().startsWith("tool result •");

const parseToolCallPreview = (block: string): { toolName: string; params: Array<{ key: string; value: string }> } => {
  const nameMatch = TOOL_NAME_REGEX.exec(block);
  const toolName = nameMatch?.[2] ?? "unknown_tool";

  const params: Array<{ key: string; value: string }> = [];
  const paramMatches = Array.from(block.matchAll(PARAM_REGEX));
  for (const match of paramMatches) {
    const key = (match[2] ?? "").trim();
    const value = (match[3] ?? "").trim();
    if (!key || !value) {
      continue;
    }
    params.push({ key, value });
  }

  return { toolName, params };
};

const StreamActivityPanel = ({
  streamEvents,
  isStreaming,
  fallbackContent,
}: {
  streamEvents: StreamEventItem[];
  isStreaming: boolean;
  fallbackContent: string;
}) => {
  const segments = streamEvents.reduce<Array<{
    id: string;
    source: StreamSource;
    label: string;
    text: string;
  }>>((acc, event) => {
    const previous = acc[acc.length - 1];
    if (
      previous &&
      previous.source === event.source &&
      previous.label === event.label
    ) {
      previous.text += event.token;
      return acc;
    }
    acc.push({
      id: event.id,
      source: event.source,
      label: event.label || sourceTone[event.source].label,
      text: event.token,
    });
    return acc;
  }, []);

  return (
    <div className="space-y-2 rounded-md border border-zinc-200 p-3 dark:border-zinc-700">
      <div className="flex items-center justify-between gap-2">
        <StreamingBadge isStreaming={isStreaming} />
      </div>
      {segments.length === 0 ? (
        fallbackContent.trim().length > 0 ? (
          <MarkdownRenderer
            content={fallbackContent}
            className="prose prose-sm dark:prose-invert max-w-none"
          />
        ) : (
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Waiting for streamed events…
          </p>
        )
      ) : (
        <div className="space-y-1">
          {segments.map((segment, index) => {
            const tone = sourceTone[segment.source];
            const isLastSegment = index === segments.length - 1;
            const toolCallBlocks = extractToolCallBlocks(segment.text);
            const hasToolCallBlocks = toolCallBlocks.length > 0;
            const isToolResult = isToolResultLabel(segment.label);
            const isSubagentResponse = segment.source === "subagent";
            const badgeNode = (
              <span className={`inline-flex rounded border px-1.5 py-0.5 font-medium ${tone.badge}`}>
                {segment.label}
              </span>
            );

            return (
              <div key={segment.id} className="space-y-1 text-xs">
                {isToolResult ? (
                  <details className="space-y-1">
                    <summary className="flex cursor-pointer list-none items-center gap-2">
                      {badgeNode}
                      <span className={DISCLOSURE_HINT_CLASS}>
                        See results
                      </span>
                    </summary>
                    <div className="mt-2">
                      <MarkdownRenderer
                        content={segment.text}
                        className="prose prose-sm dark:prose-invert max-w-none"
                      />
                      {isStreaming && isLastSegment ? (
                        <span className="ml-0.5 inline-block h-3 w-1 animate-pulse rounded-sm bg-amber-500 align-middle" />
                      ) : null}
                    </div>
                  </details>
                ) : hasToolCallBlocks ? (
                  <div className="space-y-1">
                    {badgeNode}
                    <div className="space-y-1">
                      {toolCallBlocks.map((block, blockIndex) => {
                        const preview = parseToolCallPreview(block);
                        const hasParams = preview.params.length > 0;
                        return (
                          <details
                            key={`${segment.id}-tool-call-${blockIndex}`}
                            className="space-y-1"
                          >
                            <summary className="flex cursor-pointer list-none items-center gap-2">
                              <span className={`inline-flex rounded border px-1.5 py-0.5 font-medium ${TOOL_REQUEST_BADGE_CLASS}`}>
                                Tool Request • {preview.toolName}
                              </span>
                              <span className={DISCLOSURE_HINT_CLASS}>
                                {hasParams ? "See parameters" : "See payload"}
                              </span>
                            </summary>
                            <div className="mt-2 space-y-1 rounded-md border border-zinc-700/40 bg-zinc-950/30 p-2">
                              {hasParams ? (
                                preview.params.map((param, paramIndex) => (
                                  <div key={`${segment.id}-param-${paramIndex}`} className="space-y-0.5">
                                    <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                                      {param.key}
                                    </p>
                                    <pre className="whitespace-pre-wrap break-words text-xs leading-relaxed text-zinc-200">
                                      {param.value}
                                    </pre>
                                  </div>
                                ))
                              ) : (
                                <pre className="whitespace-pre-wrap break-words text-xs leading-relaxed text-zinc-300">
                                  {block}
                                </pre>
                              )}
                            </div>
                          </details>
                        );
                      })}
                      {isStreaming && isLastSegment ? (
                        <span className="ml-0.5 inline-block h-3 w-1 animate-pulse rounded-sm bg-amber-500 align-middle" />
                      ) : null}
                    </div>
                  </div>
                ) : isSubagentResponse ? (
                  <details className="space-y-1">
                    <summary className="flex cursor-pointer list-none items-center gap-2">
                      {badgeNode}
                      <span className={DISCLOSURE_HINT_CLASS}>
                        See subagent response
                      </span>
                    </summary>
                    <div className="mt-2">
                      <MarkdownRenderer
                        content={segment.text}
                        className="prose prose-sm dark:prose-invert max-w-none"
                      />
                      {isStreaming && isLastSegment ? (
                        <span className="ml-0.5 inline-block h-3 w-1 animate-pulse rounded-sm bg-amber-500 align-middle" />
                      ) : null}
                    </div>
                  </details>
                ) : (
                  <div className="space-y-1">
                    {badgeNode}
                    <MarkdownRenderer
                      content={segment.text}
                      className="prose prose-sm dark:prose-invert max-w-none"
                    />
                    {isStreaming && isLastSegment ? (
                      <span className="ml-0.5 inline-block h-3 w-1 animate-pulse rounded-sm bg-amber-500 align-middle" />
                    ) : null}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

const ResponseDisplayComponent = ({
  content,
  streamEvents,
  isStreaming,
}: ResponseDisplayProps) => {
  const autoScrollKey = useMemo(() => {
    const streamKey = streamEvents.map(event => `${event.id}:${event.source}:${event.token}`).join("||");
    return [content, streamKey, isStreaming ? "1" : "0"].join("::");
  }, [content, streamEvents, isStreaming]);

  const { scrollRef, contentRef } = useAutoScroll(autoScrollKey);
  const hasPrimaryFlow = streamEvents.length > 0 || content.trim().length > 0 || isStreaming;
  if (!hasPrimaryFlow) {
    return null;
  }

  return (
    <Card className="w-full mt-3 flex-1 h-full overflow-hidden">
      <CardContent className="p-3 h-full pr-5">
        <ScrollArea ref={scrollRef} className="h-full w-full pr-2">
          <div ref={contentRef} className="space-y-5">
            <StreamActivityPanel
              streamEvents={streamEvents}
              isStreaming={isStreaming}
              fallbackContent={content}
            />
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export const ResponseDisplay = memo(ResponseDisplayComponent)
