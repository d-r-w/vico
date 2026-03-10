"use client"

import { memo, useMemo, useState } from "react"
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
const TOOL_CALL_BADGE_CLASS =
  "border-violet-300 bg-violet-50 text-violet-700 dark:border-violet-800 dark:bg-violet-900/30 dark:text-violet-100";

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

const stripToolCallBlocks = (text: string): string => text.replace(TOOL_CALL_BLOCK_REGEX, "").trim();

const formatPayloadForCodeBlock = (payload: unknown): string => {
  if (payload == null) {
    return "null";
  }
  if (typeof payload === "string") {
    return payload;
  }
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
};

interface ToolCallEntry {
  key: string;
  toolName: string;
  request: unknown;
  response: unknown;
}

interface StreamSegment {
  id: string;
  source: StreamSource;
  label: string;
  text: string;
}

type TimelineItem =
  | { type: "segment"; segment: StreamSegment }
  | { type: "subagent_header"; key: string; label: string }
  | { type: "tool"; toolKey: string };

const ToolCallItem = ({ entry }: { entry: ToolCallEntry }) => {
  const [isRequestOpen, setIsRequestOpen] = useState(false);
  const [isResponseOpen, setIsResponseOpen] = useState(false);
  const requestText = formatPayloadForCodeBlock(entry.request);
  const responseText = formatPayloadForCodeBlock(entry.response);
  const hasResponse = entry.response !== undefined;

  return (
    <div className="space-y-1 text-xs">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`inline-flex rounded border px-1.5 py-0.5 font-medium ${TOOL_CALL_BADGE_CLASS}`}>
          Tool Call • {entry.toolName}
        </span>
        <button
          type="button"
          onClick={() => setIsRequestOpen(prev => !prev)}
          className={`inline-flex rounded border px-1.5 py-0.5 font-medium ${TOOL_REQUEST_BADGE_CLASS}`}
        >
          Request
        </button>
        <button
          type="button"
          onClick={() => setIsResponseOpen(prev => !prev)}
          className={`inline-flex rounded border px-1.5 py-0.5 font-medium ${TOOL_RESULT_BADGE_CLASS}`}
        >
          Response
        </button>
      </div>
      {isRequestOpen ? (
        <div className="rounded-md border border-zinc-700/40 bg-zinc-950/30 p-2">
          <pre className="whitespace-pre-wrap break-words text-xs leading-relaxed text-zinc-200">
            {requestText}
          </pre>
        </div>
      ) : null}
      {isResponseOpen ? (
        <div>
          {hasResponse ? (
            typeof entry.response === "string" ? (
              <MarkdownRenderer
                content={responseText}
                className="prose prose-sm dark:prose-invert max-w-none"
              />
            ) : (
              <pre className="whitespace-pre-wrap break-words text-xs leading-relaxed text-zinc-200">
                {responseText}
              </pre>
            )
          ) : (
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              No response yet.
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
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
  const toolEntries = new Map<string, ToolCallEntry>();
  const timeline: TimelineItem[] = [];
  const subagentHeadersSeen = new Set<string>();

  for (const event of streamEvents) {
    if (event.kind === "tool_call_request") {
      const callId = event.toolCallId;
      if (!callId) {
        continue;
      }
      const toolName = event.toolName || "unknown_tool";
      if (event.source === "subagent_tool" && event.parentToolName && !subagentHeadersSeen.has(event.parentToolName)) {
        const headerKey = `subagent-header:${event.parentToolName}`;
        subagentHeadersSeen.add(event.parentToolName);
        timeline.push({
          type: "subagent_header",
          key: headerKey,
          label: `Subagent • ${event.parentToolName}`,
        });
      }
      const toolKey = `${event.source}:${callId}`;
      toolEntries.set(toolKey, {
        key: toolKey,
        toolName,
        request: event.payload,
        response: undefined,
      });
      timeline.push({ type: "tool", toolKey });
      continue;
    }

    if (event.kind === "tool_call_response") {
      const callId = event.toolCallId;
      if (!callId) {
        continue;
      }
      const toolKey = `${event.source}:${callId}`;
      if (toolEntries.has(toolKey)) {
        const existing = toolEntries.get(toolKey);
        if (existing) {
          existing.response = event.payload;
        }
      }
      continue;
    }

    const label = event.label || sourceTone[event.source].label;
    const text = event.token;
    const previous = timeline[timeline.length - 1];
    if (
      previous?.type === "segment" &&
      previous.segment.source === event.source &&
      previous.segment.label === label
    ) {
      previous.segment.text += text;
      continue;
    }
    timeline.push({
      type: "segment",
      segment: {
        id: event.id,
        source: event.source,
        label,
        text,
      },
    });
  }

  return (
    <div className="space-y-2 rounded-md border border-zinc-200 p-3 dark:border-zinc-700">
      <div className="flex items-center justify-between gap-2">
        <StreamingBadge isStreaming={isStreaming} />
      </div>
      {timeline.length === 0 ? (
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
          {timeline.map((item, index) => {
            const isLastSegment = index === timeline.length - 1;
            if (item.type === "subagent_header") {
              const subagentTone = sourceTone.subagent;
              return (
                <div key={item.key} className="space-y-1 text-xs">
                  <span className={`inline-flex rounded border px-1.5 py-0.5 font-medium ${subagentTone.badge}`}>
                    {item.label}
                  </span>
                  {isStreaming && isLastSegment ? (
                    <span className="ml-0.5 inline-block h-3 w-1 animate-pulse rounded-sm bg-amber-500 align-middle" />
                  ) : null}
                </div>
              );
            }
            if (item.type === "tool") {
              const entry = toolEntries.get(item.toolKey);
              if (!entry) {
                return null;
              }
              return (
                <div key={entry.key} className="space-y-1 text-xs">
                  <ToolCallItem entry={entry} />
                  {isStreaming && isLastSegment ? (
                    <span className="ml-0.5 inline-block h-3 w-1 animate-pulse rounded-sm bg-amber-500 align-middle" />
                  ) : null}
                </div>
              );
            }

            const segment = item.segment;
            const tone = sourceTone[segment.source];
            const isSubagentResponse = segment.source === "subagent";
            const badgeNode = (
              <span className={`inline-flex rounded border px-1.5 py-0.5 font-medium ${tone.badge}`}>
                {segment.label}
              </span>
            );
            const cleanText = stripToolCallBlocks(segment.text);
            if (!cleanText) {
              return null;
            }

            return (
              <div key={segment.id} className="space-y-1 text-xs">
                {isSubagentResponse ? (
                  <details className="space-y-1">
                    <summary className="flex cursor-pointer list-none items-center gap-2">
                      <span className={`inline-flex rounded border px-1.5 py-0.5 font-medium ${sourceTone.subagent.badge}`}>
                        Subagent Response
                      </span>
                    </summary>
                    <div className="mt-2">
                      <MarkdownRenderer
                        content={cleanText}
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
                      content={cleanText}
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

  const { scrollRef } = useAutoScroll(autoScrollKey, { isStreaming });
  const hasPrimaryFlow = streamEvents.length > 0 || content.trim().length > 0 || isStreaming;
  if (!hasPrimaryFlow) {
    return null;
  }

  return (
    <Card className="w-full mt-3 flex-1 h-full overflow-hidden">
      <CardContent className="p-3 h-full pr-5">
        <ScrollArea ref={scrollRef} className="h-full w-full pr-2">
          <div className="space-y-5">
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
