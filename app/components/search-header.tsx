"use client";

import { useRef } from "react";
import { Mode, StreamEventItem } from "@/app/types";
import { SearchInput, SearchInputHandle } from "@/app/components/search-input";
import { ThemeToggle } from "@/app/components/theme-toggle";
import { ModeToggle } from "@/app/components/mode-toggle";
import { Button } from "@/components/ui/button";
import { PanelLeft } from "lucide-react";

interface SearchHeaderProps {
  initialSearch: string;
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  onResponseReceived: (response: string) => void;
  onThinkingTokenReceived?: (assistantName: string, token: string) => void;
  onThinkingComplete?: (assistantName: string) => void;
  onToolCallStart?: (toolName: string, input?: unknown) => void;
  onToolCallEnd?: (toolName: string, output?: unknown) => void;
  onSubagentTokenReceived?: (assistantName: string, token: string) => void;
  onSubagentToolCallStart?: (parentToolName: string, toolName: string, input?: unknown) => void;
  onSubagentToolCallEnd?: (parentToolName: string, toolName: string, output?: unknown) => void;
  onStreamEvent?: (event: StreamEventItem) => void;
  onStreamingStateChange?: (isStreaming: boolean) => void;
  onToggleSidebar?: () => void;
}

export function SearchHeader({ 
  initialSearch, 
  mode, 
  onModeChange, 
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
  onToggleSidebar,
}: SearchHeaderProps) {
  const searchInputRef = useRef<SearchInputHandle>(null);

  const handleModeChange = (newMode: Mode) => {
    onModeChange(newMode);
    setTimeout(() => {
      searchInputRef.current?.focus();
    }, 0);
  };

  return (
    <header className="bg-primary text-primary-foreground py-3">
      <div className="container mx-auto px-2">
        <div className="flex flex-col sm:flex-row items-center gap-2">
          <div className="flex items-center gap-2 w-full sm:w-auto">
            {onToggleSidebar && (
              <Button variant="ghost" size="icon" onClick={onToggleSidebar} className="shrink-0">
                <PanelLeft className="h-5 w-5" />
                <span className="sr-only">Toggle Sidebar</span>
              </Button>
            )}
            <ThemeToggle />
            <ModeToggle mode={mode} onModeChange={handleModeChange} />
          </div>
          <div className="w-full">
            <SearchInput 
              ref={searchInputRef}
              initialSearch={initialSearch} 
              mode={mode} 
              onResponseReceived={onResponseReceived}
              onThinkingTokenReceived={onThinkingTokenReceived}
              onThinkingComplete={onThinkingComplete}
              onToolCallStart={onToolCallStart}
              onToolCallEnd={onToolCallEnd}
              onSubagentTokenReceived={onSubagentTokenReceived}
              onSubagentToolCallStart={onSubagentToolCallStart}
              onSubagentToolCallEnd={onSubagentToolCallEnd}
              onStreamEvent={onStreamEvent}
              onStreamingStateChange={onStreamingStateChange}
            />
          </div>
        </div>
      </div>
    </header>
  );
}
