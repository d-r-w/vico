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
    <header className="bg-primary text-primary-foreground py-3">
      <div className="container mx-auto px-2">
        <div className="flex items-center gap-2">
          <ModeToggle mode={mode} onModeChange={handleModeChange} />
          <div className="flex-grow">
              <SearchInput 
                ref={searchInputRef}
                initialSearch={initialSearch} 
                mode={mode} 
                onResponseReceived={setResponse}
              />
            </div>
          <ThemeToggle />
        </div>
        {response && <ResponseDisplay content={response} />}
      </div>
    </header>
  );
} 