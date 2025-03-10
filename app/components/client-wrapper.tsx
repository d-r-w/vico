"use client";

import { useState, useEffect, useRef } from "react";
import { MODES, Mode } from "@/app/types";
import { ResponseDisplay } from "@/app/components/response-display";
import { SearchHeader } from "@/app/components/search-header";
import { SearchInputHandle } from "@/app/components/search-input";

interface ClientWrapperProps {
  initialSearch: string;
}

export function ClientWrapper({ initialSearch }: ClientWrapperProps) {
  const [response, setResponse] = useState<string>("");
  const [mode, setMode] = useState<Mode>(MODES.SEARCH);
  const searchInputRef = useRef<SearchInputHandle>(null);
  
  useEffect(() => {
    searchInputRef.current?.focus();
  }, []);

  return (
    <div className="flex flex-col h-full">
      <SearchHeader 
        initialSearch={initialSearch}
        mode={mode}
        onModeChange={setMode}
        onResponseReceived={setResponse}
      />
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