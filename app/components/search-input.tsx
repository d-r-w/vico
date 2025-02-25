"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Mode, MODES } from "@/app/types";

interface SearchInputProps {
  initialSearch?: string;
  mode: Mode;
  onResponseReceived?: (response: string) => void;
}

export default function SearchInput({ initialSearch = "", mode, onResponseReceived }: SearchInputProps) {
  const [search, setSearch] = useState(initialSearch);
  const router = useRouter();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearch(value);
    if (mode === MODES.SEARCH) {
      router.push(`/?search=${encodeURIComponent(value)}`);
    }
  };

  const handleKeyDown = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    const value = e.currentTarget.value;
    if ((mode === MODES.CHAT || mode === MODES.DEEP) && e.key === 'Enter') {
      try {
        const response = await fetch('/api/memories/probe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            query: value,
            deep: mode === MODES.DEEP
          }),
        });
        
        if (!response.ok) throw new Error('Failed to probe memories');
        
        const result = await response.json();
        onResponseReceived?.(result.response);
      } catch (error) {
        console.error('Failed to probe memories:', error);
      }
    }
  };

  const getPlaceholder = () => {
    switch (mode) {
      case MODES.SEARCH:
        return "Search memories...";
      case MODES.CHAT:
        return "Ask about your memories...";
      case MODES.DEEP:
        return "Delve into your memories...";
      default:
        return "Search memories...";
    }
  };

  return (
    <div className="flex gap-2">
      <Input
        type={mode === MODES.SEARCH ? "search" : "text"}
        name={mode}
        autoComplete="off"
        placeholder={getPlaceholder()}
        value={search}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        className="flex-grow"
      />
    </div>
  );
}