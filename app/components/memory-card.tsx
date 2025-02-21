"use client";

import { useState, useRef, useEffect } from "react";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import { CalendarIcon, Trash } from "lucide-react";
import Image from "next/image";
import type { Memory } from "@/app/types";

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

export function MemoryCard({ memory }: { memory: Memory }) {
  const [isDeleted, setIsDeleted] = useState(false);
  const [hasDeleteError, setHasDeleteError] = useState(false);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

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
      className="w-full max-w-md h-[32rem] flex flex-col transition-all duration-300 hover:shadow-lg"
    >
      <CardHeader className="flex justify-between items-center">
        <CardTitle className="text-lg font-semibold line-clamp-2">
          {memory.memory?.split("\n")[0]}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col flex-grow overflow-hidden">
        {memory.image && (
          <div className="relative w-full h-[48rem] mb-4">
            <Image
              src={`data:image/png;base64,${memory.image}`}
              alt="Memory image"
              fill
              className="object-cover rounded-md"
            />
          </div>
        )}
        <div className="flex-grow overflow-y-auto pr-2">
          <p className="text-sm text-muted-foreground whitespace-pre-wrap">
            {memory.memory}
          </p>
        </div>
      </CardContent>
      <CardFooter className="mt-auto">
        <div className="flex items-center text-sm text-muted-foreground">
          <CalendarIcon className="w-4 h-4 mr-2" />
          <time dateTime={memory.created_at}>
            {dateTimeFormat.format(new Date(memory.created_at))}
          </time>
        </div>
        <button
          type="button"
          onClick={handleTrashClick}
          className={`ml-auto p-2 hover:text-white ${
            isConfirmingDelete
              ? "rounded-full text-white bg-orange-500"
              : "hover:rounded-full hover:bg-red-700"
          } text-red-500 ${hasDeleteError ? "animate-shake" : ""}`}
          aria-label="Delete memory"
        >
          <Trash size={20} />
        </button>
      </CardFooter>
    </Card>
  );
}
