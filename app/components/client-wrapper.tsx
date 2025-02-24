"use client";

import { useState } from "react";
import SearchInput from "./search-input";
import { ResponseDisplay } from "@/components/response-display";
import { MODES, Mode } from "@/app/types";
import { ThemeToggle } from "@/components/theme-toggle";
import { SearchOrChatToggle } from "./search-or-chat-toggle";

interface ClientWrapperProps {
  initialSearch: string;
}

export function ClientWrapper({ initialSearch }: ClientWrapperProps) {
  const [response, setResponse] = useState<string>("");
  const [mode, setMode] = useState<Mode>(MODES.SEARCH);

  return (
    <header className="bg-primary text-primary-foreground py-6">
      <div className="container mx-auto px-4">
        <div className="flex items-center gap-4">
          <SearchOrChatToggle mode={mode} onModeChange={setMode} />
          <div className="flex-grow">
              <SearchInput 
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