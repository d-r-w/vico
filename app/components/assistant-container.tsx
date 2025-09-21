"use client"

import { memo } from "react"
import { ThinkingBox } from "@/app/components/thinking-box";

interface AssistantContainerProps {
  assistantName: string;
  thinkingBlocks: Array<{
    content: string;
    isComplete: boolean;
  }>;
  children?: React.ReactNode;
}

const AssistantContainerComponent = ({ 
  assistantName, 
  thinkingBlocks, 
  children 
}: AssistantContainerProps) => {
  if (thinkingBlocks.length === 0 && !children) return null;

  return (
    <div className="mt-4 rounded-lg border border-orange-200 dark:border-orange-800 bg-orange-50 dark:bg-orange-950/20 p-4">
      {/* Assistant header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-3 h-3 rounded-full bg-orange-500"></div>
        <span className="text-sm font-medium text-orange-700 dark:text-orange-300">
          {assistantName}
        </span>
      </div>
      
      {/* Thinking blocks */}
      <div className="space-y-2">
        {thinkingBlocks.map((block, index) => (
          <ThinkingBox 
            key={index}
            content={block.content}
            toolName={assistantName}
            isComplete={block.isComplete}
          />
        ))}
        
        {/* Additional content like tool calls */}
        {children}
      </div>
    </div>
  );
}

export const AssistantContainer = memo(AssistantContainerComponent)
