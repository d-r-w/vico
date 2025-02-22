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

const MemoryTextarea = React.memo(({ value, onChange }: {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
}) => (
  <Textarea
    value={value}
    onChange={onChange}
    className="w-full h-full resize-none bg-transparent hover:bg-accent/10 focus:bg-background transition-colors duration-200 overflow-y-auto"
    placeholder="Write your memory..."
  />
));

MemoryTextarea.displayName = "MemoryTextarea";

export function MemoryCard({ memory }: { memory: Memory }) {
  const [isDeleted, setIsDeleted] = useState(false);
  const [hasDeleteError, setHasDeleteError] = useState(false);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [editedMemory, setEditedMemory] = useState(memory.memory);
  const [isSaving, setIsSaving] = useState(false);
  const [hasSaveError, setHasSaveError] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasChanges = editedMemory !== memory.memory;

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  const handleSave = async () => {
    if (!hasChanges) {
      return;
    }

    setIsSaving(true);
    try {
      const res = await fetch('/api/memories', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id: memory.id,
          memory: editedMemory,
        }),
      });

      if (!res.ok) {
        throw new Error('Failed to save');
      }

      memory.memory = editedMemory;
    } catch (err) {
      console.error('Failed to save memory:', err);
      setHasSaveError(true);
      setTimeout(() => setHasSaveError(false), 1000);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    setIsConfirmingDelete(false);

    const res = await fetch(`/api/memories?id=${memory.id}`, {
      method: "DELETE"
    });
    if (res.ok) {
      setIsDeleted(true);
    } else {
      setHasDeleteError(true);
      setTimeout(() => setHasDeleteError(false), 1000);
    }
  };

  const handleTrashClick = () => {
    if (isConfirmingDelete) {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      handleDelete();
    } else {
      setIsConfirmingDelete(true);
      timerRef.current = setTimeout(() => {
        setIsConfirmingDelete(false);
      }, 2000);
    }
  };

  if (isDeleted) return null;

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
        {memory.image ? (
          <div style={{ display: "flex", flexDirection: "column" }} className="grid grid-rows-[1fr,auto] h-full gap-4">
            <div style={{ display: "flex" }} className="min-h-[10rem] relative w-full min-h-0">
              <Image
                src={`data:image/png;base64,${memory.image}`}
                alt="Memory image"
                fill
                className="object-cover rounded-md"
              />
            </div>
            <MemoryTextarea 
              value={editedMemory}
              onChange={(e) => setEditedMemory(e.target.value)}
            />
          </div>
        ) : (
          <MemoryTextarea 
            value={editedMemory}
            onChange={(e) => setEditedMemory(e.target.value)}
          />
        )}
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
              disabled={isSaving}
              className={`p-2 ${
                isSaving
                  ? "text-gray-400"
                  : hasSaveError
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
            className={`p-2 hover:text-white ${
              isConfirmingDelete
                ? "rounded-full text-white bg-orange-500"
                : "hover:rounded-full hover:bg-red-700"
            } text-red-500 ${hasDeleteError ? "animate-shake" : ""} transition-all duration-200`}
            aria-label="Delete memory"
          >
            <Trash size={20} />
          </button>
        </div>
      </CardFooter>
    </Card>
  );
}
