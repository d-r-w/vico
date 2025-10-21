"use client"

import { memo, useMemo, type ReactNode } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { MarkdownRenderer } from "@/app/components/markdown-renderer"
import { useAutoScroll } from "@/app/hooks/useAutoScroll"
import type { ThinkingBlock, ToolCallState } from "@/app/types"

interface ResponseDisplayProps {
  content: string;
  assistantThinking: ThinkingBlock[];
  toolCalls: ToolCallState[];
}

interface SectionData {
  id: string;
  title: string;
  badge?: ReactNode;
  contextLabel?: string;
  content?: ReactNode;
}

const statusLabels: Record<ToolCallState["state"], string> = {
  default: "pending",
  loading: "running",
  ready: "done",
  error: "error",
};

const statusDot: Record<ToolCallState["state"], string> = {
  default: "bg-zinc-400",
  loading: "bg-amber-500 animate-pulse",
  ready: "bg-emerald-500",
  error: "bg-rose-500",
};

const statusText: Record<ToolCallState["state"], string> = {
  default: "text-zinc-500",
  loading: "text-amber-600",
  ready: "text-emerald-600",
  error: "text-rose-600",
};

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

const StatusBadge = ({ state }: { state: ToolCallState["state"] }) => (
  <span
    className={`inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide ${
      statusText[state]
    }`}
  >
    <span className={`w-1.5 h-1.5 rounded-full ${statusDot[state]}`} />
    {statusLabels[state]}
  </span>
);

const safeStringify = (value: unknown) => {
  if (value === undefined) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const joinThinkingBlocks = (blocks: ThinkingBlock[]) =>
  blocks.map(block => block.content).join(blocks.length > 1 ? "\n\n" : "");

const buildThinkingSection = (
  id: string,
  heading: string,
  blocks: ThinkingBlock[],
): SectionData | null => {
  if (blocks.length === 0) {
    return null;
  }

  const content = joinThinkingBlocks(blocks).trim();
  if (content.length === 0) {
    return null;
  }

  const isStreaming = blocks.some(block => !block.isComplete);

  return {
    id,
    title: heading,
    badge: <StreamingBadge isStreaming={isStreaming} />,
    content: (
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
        {content}
      </p>
    ),
  };
};

const renderToolCallBody = (call: ToolCallState) => {
  const pieces: ReactNode[] = [];
  const hasInput = call.input !== undefined && call.input !== null;
  const hasOutput = call.output !== undefined && call.output !== null;

  if (hasInput) {
    pieces.push(
      <div key="input" className="space-y-1">
        <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Input
        </span>
        <pre className="whitespace-pre-wrap text-xs font-mono leading-relaxed text-zinc-700 dark:text-zinc-200">
          {safeStringify(call.input)}
        </pre>
      </div>,
    );
  }

  if (hasOutput) {
    pieces.push(
      <div key="output" className="space-y-1">
        <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Output
        </span>
        <pre className="whitespace-pre-wrap text-xs font-mono leading-relaxed text-zinc-700 dark:text-zinc-200">
          {safeStringify(call.output)}
        </pre>
      </div>,
    );
  }

  if (!pieces.length && call.state === "loading") {
    pieces.push(
      <p key="pending" className="text-xs italic text-zinc-500 dark:text-zinc-400">
        Waiting for tool output…
      </p>,
    );
  }

  if (!pieces.length) {
    return null;
  }

  return <div className="space-y-3">{pieces}</div>;
};

const buildToolCallSections = (
  call: ToolCallState,
  contextChain: string[] = [],
): SectionData[] => {
  const sections: SectionData[] = [];
  const contextLabel = contextChain.length ? `via ${contextChain.join(" → ")}` : undefined;

  sections.push({
    id: `${call.id}-tool`,
    title: `Tool • ${call.toolName}`,
    contextLabel,
    badge: <StatusBadge state={call.state} />,
    content: renderToolCallBody(call),
  });

  if (call.subagent) {
    const { name, thinkingBlocks, chat, toolCalls: nestedCalls } = call.subagent;

    const subagentThinking = buildThinkingSection(
      `${call.id}-subagent-thinking`,
      `Subagent thinking • ${name}`,
      thinkingBlocks,
    );

    if (subagentThinking) {
      sections.push(subagentThinking);
    }

    if (chat.trim().length > 0) {
      sections.push({
        id: `${call.id}-subagent-chat`,
        title: `Subagent • ${name}`,
        content: (
          <MarkdownRenderer
            content={chat}
            className="prose prose-sm dark:prose-invert max-w-none"
          />
        ),
      });
    }

    nestedCalls.forEach(nested => {
      sections.push(...buildToolCallSections(nested, [...contextChain, name]));
    });
  }

  return sections;
};

const stringifyThinkingBlocks = (blocks: ThinkingBlock[]) =>
  blocks.map(block => `${block.content}:${block.isComplete ? "1" : "0"}`).join("|");

const toolCallKeyForAutoScroll = (call: ToolCallState): string => {
  const parts = [
    call.id,
    call.toolName,
    call.state,
    safeStringify(call.input),
    safeStringify(call.output),
  ];

  if (call.subagent) {
    parts.push(
      call.subagent.name,
      call.subagent.chat,
      stringifyThinkingBlocks(call.subagent.thinkingBlocks),
      call.subagent.toolCalls.map(toolCallKeyForAutoScroll).join("&"),
    );
  }

  return parts.join("::");
};

const Section = ({
  title,
  badge,
  contextLabel,
  content,
  step,
}: SectionData & { step: number }) => (
  <div className="flex gap-3">
    <div className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-zinc-200 text-[11px] font-semibold text-zinc-700 dark:bg-zinc-700 dark:text-zinc-100">
      {step + 1}
    </div>
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        <span>{title}</span>
        {contextLabel ? (
          <span className="text-[10px] font-medium uppercase text-zinc-400 dark:text-zinc-500">
            {contextLabel}
          </span>
        ) : null}
        {badge}
      </div>
      {content ? (
        <div className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-200">
          {content}
        </div>
      ) : null}
    </div>
  </div>
);

const ResponseDisplayComponent = ({ content, assistantThinking, toolCalls }: ResponseDisplayProps) => {
  const autoScrollKey = useMemo(() => {
    const assistantKey = stringifyThinkingBlocks(assistantThinking);
    const toolKey = toolCalls.map(toolCallKeyForAutoScroll).join("||");
    return [content, assistantKey, toolKey].join("::");
  }, [assistantThinking, toolCalls, content]);

  const { scrollRef, contentRef } = useAutoScroll(autoScrollKey);

  const sections = useMemo(() => {
    const items: SectionData[] = [];

    const assistantThinkingSection = buildThinkingSection(
      "assistant-thinking",
      "Assistant thinking",
      assistantThinking,
    );

    if (assistantThinkingSection) {
      items.push(assistantThinkingSection);
    }

    toolCalls.forEach(call => {
      items.push(...buildToolCallSections(call));
    });

    if (content.trim().length > 0) {
      items.push({
        id: "assistant-response",
        title: "Assistant",
        content: (
          <MarkdownRenderer
            content={content}
            className="prose prose-sm dark:prose-invert max-w-none"
          />
        ),
      });
    }

    return items;
  }, [content, assistantThinking, toolCalls]);

  if (sections.length === 0) {
    return null;
  }

  return (
    <Card className="w-full mt-3 flex-1 h-full overflow-hidden">
      <CardContent className="p-3 h-full pr-5">
        <ScrollArea ref={scrollRef} className="h-full w-full pr-2">
          <div ref={contentRef} className="space-y-5">
            {sections.map((section, index) => (
              <Section key={section.id} step={index} {...section} />
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export const ResponseDisplay = memo(ResponseDisplayComponent)
