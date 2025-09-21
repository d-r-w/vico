"use client"

import { useRef, useEffect, memo } from "react";

interface ThinkingBoxProps {
  content: string;
  toolName?: string;
  isComplete?: boolean;
}

const ThinkingBoxComponent = ({ content, toolName, isComplete = false }: ThinkingBoxProps) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    ref.current.scrollTop = ref.current.scrollHeight;
  }, [content]);

  if (!content || content.trim().length === 0) return null;

  return (
    <div
      ref={ref}
      className="mt-2 rounded border border-zinc-300 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 text-xs text-zinc-600 dark:text-zinc-400"
    >
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-2 h-2 rounded-full ${
          isComplete 
            ? "bg-green-500" 
            : "bg-orange-500 animate-pulse"
        }`}></div>
        <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
          {isComplete 
            ? (toolName ? `${toolName} thought` : "thought")
            : (toolName ? `${toolName} thinking...` : "thinking...")
          }
        </span>
      </div>
      <div className="text-xs text-zinc-500 dark:text-zinc-500 whitespace-pre-wrap">
        {content}
      </div>
    </div>
  );
}

export const ThinkingBox = memo(ThinkingBoxComponent)
