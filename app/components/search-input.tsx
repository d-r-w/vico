"use client";

import { useState, useRef, forwardRef, useImperativeHandle, useEffect } from "react";
import { useRouter } from "next/navigation";

import { Input } from "@/components/ui/input";
import { Mode, MODES } from "@/app/types";
import { Loader2 } from "lucide-react";

interface SearchInputProps {
  initialSearch?: string;
  mode: Mode;
  onResponseReceived?: (response: string) => void;
}

export interface SearchInputHandle {
  focus: () => void;
}

const SearchInput = forwardRef<SearchInputHandle, SearchInputProps>(
  ({ initialSearch = "", mode, onResponseReceived }, ref) => {
    const [search, setSearch] = useState(initialSearch);
    const router = useRouter();
    const inputRef = useRef<HTMLInputElement>(null);
    const prevModeRef = useRef(mode);
    const [isLoading, setIsLoading] = useState(false);

    useImperativeHandle(ref, () => ({
      focus: () => {
        inputRef.current?.focus();
      }
    }));

    useEffect(() => {
      if (prevModeRef.current !== mode) {
        setSearch('');
        router.push('/');
        prevModeRef.current = mode;
      }
    }, [mode, router]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setSearch(value);
      if (mode === MODES.SEARCH) {
        router.push(`/?search=${encodeURIComponent(value)}`);
      }
    };

    const handleSubmit = async (value: string) => {
      if (mode === MODES.CHAT || mode === MODES.DEEP) {
        try {
          setIsLoading(true);
          onResponseReceived?.('');
          
          const response = await fetch('/api/memories/probe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              query: value,
              isDeep: mode === MODES.DEEP
            }),
          });
          
          if (!response.ok) throw new Error('Failed to probe memories');
          
          const reader = response.body?.getReader();
          if (!reader) throw new Error('Response body is null');
          
          const decoder = new TextDecoder();
          let accumulatedResponse = '';
          
          while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
              break;
            }
            
            const chunk = decoder.decode(value, { stream: true });
            accumulatedResponse += chunk;
            
            onResponseReceived?.(accumulatedResponse);
          }
        } catch (error) {
          console.error('Failed to probe memories:', error);
          onResponseReceived?.('Error: Failed to retrieve response');
        } finally {
          setIsLoading(false);
        }
      }
    };

    const handleKeyDown = async (e: React.KeyboardEvent<HTMLInputElement>) => {
      const value = e.currentTarget.value;
      
      if (e.key === 'Escape') {
        setSearch('');
        if (mode === MODES.SEARCH) {
          router.push('/');
        }
        return;
      }
      
      if ((mode === MODES.CHAT || mode === MODES.DEEP) && e.key === 'Enter') {
        e.preventDefault();
        await handleSubmit(value);
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
      <>
        {isLoading ? (
          <div className="flex justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <form 
            className="flex gap-2 relative"
            onSubmit={async (e) => {
              e.preventDefault();
              await handleSubmit(search);
            }}
          >
            <Input
              ref={inputRef}
              type={mode === MODES.SEARCH ? "search" : "text"}
              name={mode}
              autoComplete="off"
              placeholder={getPlaceholder()}
              value={search}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              className="flex-grow"
            />
          </form>
        )}
      </>
    );
  }
);

SearchInput.displayName = "SearchInput";
export { SearchInput };