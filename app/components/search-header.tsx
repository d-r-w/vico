"use client";

import { useRef } from "react";
import { Mode } from "@/app/types";
import { SearchInput, SearchInputHandle } from "@/app/components/search-input";
import { ThemeToggle } from "@/app/components/theme-toggle";
import { ModeToggle } from "@/app/components/mode-toggle";

interface SearchHeaderProps {
  initialSearch: string;
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  onResponseReceived: (response: string) => void;
}

export function SearchHeader({ 
  initialSearch, 
  mode, 
  onModeChange, 
  onResponseReceived 
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
            <ThemeToggle />
            <ModeToggle mode={mode} onModeChange={handleModeChange} />
          </div>
          <div className="w-full">
            <SearchInput 
              ref={searchInputRef}
              initialSearch={initialSearch} 
              mode={mode} 
              onResponseReceived={onResponseReceived}
            />
          </div>
        </div>
      </div>
    </header>
  );
} 