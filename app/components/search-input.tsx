"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Mode, MODES } from "@/app/types";

interface SearchInputProps {
  initialSearch?: string;
  mode: Mode;
}

export default function SearchInput({ initialSearch = "", mode }: SearchInputProps) {
  const [search, setSearch] = useState(initialSearch);
  const router = useRouter();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearch(value);
    if (mode === MODES.SEARCH) {
      router.push(`/?search=${encodeURIComponent(value)}`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (mode === MODES.CHAT && e.key === 'Enter') {
      console.log("Chat input:", e.currentTarget.value);
    }
  };

  return (
    <div className="flex gap-2">
      <Input
        type={mode === MODES.SEARCH ? "search" : "text"}
        name={mode}
        autoComplete="off"
        placeholder={mode === MODES.SEARCH ? "Search memories..." : "Ask about your memories..."}
        value={search}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        className="flex-grow"
      />
    </div>
  );
}