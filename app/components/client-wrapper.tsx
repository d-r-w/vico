"use client";

import { useState, useRef, useEffect } from "react";

import { MODES, Mode } from "@/app/types";
import { SearchInput, SearchInputHandle } from "@/app/components/search-input";
import { ResponseDisplay } from "@/app/components/response-display";
import { ThemeToggle } from "@/app/components/theme-toggle";
import { ModeToggle } from "@/app/components/mode-toggle";

interface ClientWrapperProps {
  initialSearch: string;
}

export function ClientWrapper({ initialSearch }: ClientWrapperProps) {
  const [response, setResponse] = useState<string>("");
  const [mode, setMode] = useState<Mode>(MODES.SEARCH);
  const searchInputRef = useRef<SearchInputHandle>(null);

  const handleModeChange = (newMode: Mode) => {
    setMode(newMode);
    setTimeout(() => {
      searchInputRef.current?.focus();
    }, 0);
  };

  useEffect(() => {
    searchInputRef.current?.focus();
  }, []);

  return (
    <div className="flex flex-col h-full">
      <header className="bg-primary text-primary-foreground py-3">
        <div className="container mx-auto px-2">
          <div className="flex flex-col sm:flex-row items-center gap-2">
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <ThemeToggle />
              <ModeToggle mode={mode} onModeChange={handleModeChange} />
            </div>
            <div className="w-full">
              <SearchInput 
                ref={searchInputRef}
                initialSearch={initialSearch} 
                mode={mode} 
                onResponseReceived={setResponse}
              />
            </div>
          </div>
        </div>
      </header>
      <div className="container mx-auto px-3 flex-1 flex flex-col h-[calc(100%-3.5rem)] pb-3">
        {response ? (
          <div className="h-full flex-1">
            <ResponseDisplay content={response} />
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <p>Enter a prompt above to get started</p>
          </div>
        )}
      </div>
    </div>
  );
} 