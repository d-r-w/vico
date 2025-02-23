"use client";

import { useState } from "react";
import SearchInput from "@/app/components/search-input";
import { SearchOrChatToggle } from "@/app/components/search-or-chat-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { Mode, MODES } from "@/app/types";

interface ClientWrapperProps {
  initialSearch: string;
}

export function ClientWrapper({ initialSearch }: ClientWrapperProps) {
  const [mode, setMode] = useState<Mode>(MODES.SEARCH);

  return (
    <header className="bg-primary text-primary-foreground py-6">
      <div className="container mx-auto px-4">
        <div className="flex items-center gap-4">
          <SearchOrChatToggle mode={mode} onModeChange={setMode} />
          <div className="flex-grow">
            <SearchInput initialSearch={initialSearch} mode={mode} />
          </div>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
} 