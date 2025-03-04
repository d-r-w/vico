"use client";

import { Search, MessageSquare, Telescope } from "lucide-react";

import { MODES, Mode } from "@/app/types";
import { Button } from "@/components/ui/button";

interface ModeToggleProps {
  mode: Mode;
  onModeChange: (mode: Mode) => void;
}

export function ModeToggle({ mode, onModeChange }: ModeToggleProps) {
  return (
    <div className="flex rounded-md overflow-hidden border border-input">
      <Button
        variant={mode === MODES.SEARCH ? "default" : "ghost"}
        size="sm"
        onClick={() => onModeChange(MODES.SEARCH)}
        className={`${
          mode === MODES.SEARCH 
            ? "bg-secondary text-secondary-foreground hover:bg-secondary/90" 
            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        }`}
      >
        <Search className="h-4 w-4 mr-2" />
        Search
      </Button>
      <Button
        variant={mode === MODES.CHAT ? "default" : "ghost"}
        size="sm"
        onClick={() => onModeChange(MODES.CHAT)}
        className={`${
          mode === MODES.CHAT 
            ? "bg-secondary text-secondary-foreground hover:bg-secondary/90" 
            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        }`}
      >
        <MessageSquare className="h-4 w-4 mr-2" />
        Chat
      </Button>
      <Button
        variant={mode === MODES.DEEP ? "default" : "ghost"}
        size="sm"
        onClick={() => onModeChange(MODES.DEEP)}
        className={`${
          mode === MODES.DEEP 
            ? "bg-secondary text-secondary-foreground hover:bg-secondary/90" 
            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        }`}
      >
        <Telescope className="h-4 w-4 mr-2" />
        Deep
      </Button>
    </div>
  );
} 