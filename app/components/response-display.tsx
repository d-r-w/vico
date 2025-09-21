"use client"

import { memo } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { MarkdownRenderer } from "@/app/components/markdown-renderer"
import { AssistantContainer } from "@/app/components/assistant-container"
import { ToolCallRenderer } from "@/app/components/tool-call-renderer"
import { useAutoScroll } from "@/app/hooks/useAutoScroll"
import { AssistantThinking } from "@/app/types"

interface ToolCall {
  toolName: string;
  state: "loading" | "ready" | "error" | "default";
  input?: unknown;
  output?: unknown;
}

type TimelineItem =
  | { kind: 'assistant'; assistantName: string; blocks: { content: string; isComplete: boolean }[] }
  | { kind: 'tool_call'; toolName: string; state: "loading" | "ready" | "error" | "default"; input?: unknown; output?: unknown };

interface ResponseDisplayProps {
  content: string;
  assistantThinking?: AssistantThinking;
  toolCalls?: ToolCall[];
  timeline?: TimelineItem[];
}

const ResponseDisplayComponent = ({ 
  content, 
  assistantThinking = {}, 
  toolCalls = [],
  timeline = []
}: ResponseDisplayProps) => {
  const { scrollRef, contentRef } = useAutoScroll(content)
  
  return (
    <Card className="w-full mt-3 flex-1 h-full overflow-hidden">
      <CardContent className="p-3 h-full pr-5">
        <ScrollArea ref={scrollRef} className="h-full w-full pr-2">
          <div ref={contentRef} className="space-y-4">
            {/* Chronological timeline rendering if provided */}
            {timeline.length > 0 ? (
              timeline.map((item, index) => {
                if (item.kind === 'assistant') {
                  return (
                    <AssistantContainer
                      key={`assistant-${index}-${item.assistantName}`}
                      assistantName={item.assistantName}
                      thinkingBlocks={item.blocks}
                    />
                  )
                }
                return (
                  <ToolCallRenderer
                    key={`tool-${index}-${item.toolName}`}
                    toolCall={{
                      toolName: item.toolName,
                      state: item.state,
                      input: item.input,
                      output: item.output,
                    }}
                  />
                )
              })
            ) : (
              // Fallback to legacy grouped rendering
              Object.entries(assistantThinking).map(([assistantName, thinkingBlocks]) => (
                <AssistantContainer
                  key={assistantName}
                  assistantName={assistantName}
                  thinkingBlocks={thinkingBlocks}
                >
                  {assistantName !== "Assistant" && toolCalls
                    .filter(tc => tc.toolName === assistantName)
                    .map((toolCall, index) => (
                      <ToolCallRenderer key={`${toolCall.toolName}-${index}`} toolCall={toolCall} />
                    ))
                  }
                </AssistantContainer>
              ))
            )}
            
            {/* Main response content */}
            {content && (
              <div className="text-zinc-900 dark:text-zinc-100">
                <MarkdownRenderer content={content} />
              </div>
            )}
            
            {timeline.length === 0 && toolCalls.filter(tc => !assistantThinking[tc.toolName]).length > 0 && (
              <div className="mt-2">
                {toolCalls
                  .filter(tc => !assistantThinking[tc.toolName])
                  .map((toolCall, index) => (
                    <ToolCallRenderer key={`${toolCall.toolName}-${index}`} toolCall={toolCall} />
                  ))
                }
              </div>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

export const ResponseDisplay = memo(ResponseDisplayComponent)