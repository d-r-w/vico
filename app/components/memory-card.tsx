"use client";

import { useState, useRef, useEffect } from "react";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import { CalendarIcon, Trash, Save } from "lucide-react";
import Image from "next/image";
import type { Memory } from "@/app/types";
import { Textarea } from "../../components/ui/textarea";
import React from "react";

const dateTimeFormat = new Intl.DateTimeFormat("sv-SE", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
  timeZone: "UTC"
});

interface MemoryTextareaProps {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
}

function MemoryTextarea({ value, onChange }: MemoryTextareaProps) {
  return (
    <Textarea
      value={value}
      onChange={onChange}
      className="w-full h-full resize-none bg-transparent hover:bg-accent/10 focus:bg-background transition-colors duration-200 overflow-y-auto"
      placeholder="Write your memory..."
    />
  );
}

type Timer = ReturnType<typeof setTimeout>;

interface MemoryCardProps {
  memory: Memory;
}

export function MemoryCard({ memory }: MemoryCardProps) {
  const [deleteState, setDeleteState] = useState({
    isDeleted: false,
    hasError: false,
    isConfirming: false
  });
  const [saveState, setSaveState] = useState({
    isSaving: false,
    hasError: false
  });
  const [editedMemory, setEditedMemory] = useState(memory.memory);
  
  const timerRef = useRef<Timer>();
  const hasChanges = editedMemory !== memory.memory;

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  const handleSave = async () => {
    if (!hasChanges) return;

    setSaveState(prev => ({ ...prev, isSaving: true }));
    try {
      const res = await fetch('/api/memories', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: memory.id, memory: editedMemory }),
      });

      if (!res.ok) throw new Error('Failed to save');
      memory.memory = editedMemory;
    } catch (err) {
      console.error('Failed to save memory:', err);
      setSaveState(prev => ({ ...prev, hasError: true }));
      setTimeout(() => setSaveState(prev => ({ ...prev, hasError: false })), 1000);
    } finally {
      setSaveState(prev => ({ ...prev, isSaving: false }));
    }
  };

  const handleDelete = async () => {
    setDeleteState(prev => ({ ...prev, isConfirming: false }));

    const res = await fetch(`/api/memories?id=${memory.id}`, {
      method: "DELETE"
    });
    if (res.ok) {
      setDeleteState(prev => ({ ...prev, isDeleted: true }));
    } else {
      setDeleteState(prev => ({ ...prev, hasError: true }));
      setTimeout(() => setDeleteState(prev => ({ ...prev, hasError: false })), 1000);
    }
  };

  const handleTrashClick = () => {
    if (deleteState.isConfirming) {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = undefined;
      }
      handleDelete();
    } else {
      setDeleteState(prev => ({ ...prev, isConfirming: true }));
      timerRef.current = setTimeout(() => {
        setDeleteState(prev => ({ ...prev, isConfirming: false }));
      }, 1500);
    }
  };

  if (deleteState.isDeleted) return null;

  return (
    <Card
      key={memory.id}
      className="w-full max-w-md h-[32rem] flex flex-col"
    >
      <CardHeader className="flex justify-between items-center flex-none">
        <CardTitle className="text-lg font-semibold line-clamp-2">
          {editedMemory?.split("\n")[0]}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col min-h-0">
        <div className="flex flex-col h-full gap-4">
          {memory.image && (
            <div className="flex-1 relative w-full min-h-[10rem] border border-gray-200 rounded-md">
              <Image
                src={`data:image/png;base64,${memory.image}`}
                alt="Memory image"
                fill
                className="object-contain rounded-md"
              />
            </div>
          )}
          <MemoryTextarea 
            value={editedMemory}
            onChange={(e) => setEditedMemory(e.target.value)}
          />
        </div>
      </CardContent>
      <CardFooter className="flex-none">
        <div className="flex items-center text-sm text-muted-foreground">
          <CalendarIcon className="w-4 h-4 mr-2" />
          <time dateTime={memory.created_at}>
            {dateTimeFormat.format(new Date(memory.created_at))}
          </time>
        </div>
        <div className="ml-auto flex gap-2">
          {hasChanges && (
            <button
              type="button"
              onClick={handleSave}
              disabled={saveState.isSaving}
              className={`p-2 ${
                saveState.isSaving
                  ? "text-gray-400"
                  : saveState.hasError
                  ? "animate-shake text-red-500"
                  : "text-green-500 hover:text-white hover:bg-green-700 hover:rounded-full"
              } transition-all duration-200`}
              aria-label="Save memory"
            >
              <Save size={20} />
            </button>
          )}
          <button
            type="button"
            onClick={handleTrashClick}
            className={`p-2 transition-all duration-200 ${
              deleteState.isConfirming
                ? "rounded-full bg-red-500 hover:bg-red-500 animate-confirm-delete"
                : "text-red-500 hover:text-white hover:bg-red-700 hover:rounded-full"
            } ${deleteState.hasError ? "animate-shake" : ""}`}
            aria-label={deleteState.isConfirming ? "Click again to confirm delete" : "Delete memory"}
          >
            <Trash 
              size={20} 
              className={`${deleteState.isConfirming ? " text-white animate-bounce-subtle" : ""}`}
            />
          </button>
        </div>
      </CardFooter>
    </Card>
  );
}
