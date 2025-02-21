import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import { CalendarIcon } from "lucide-react";
import Image from "next/image";
import { Skeleton } from "@/components/ui/skeleton";
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
  return (
    <Card
      key={memory.id}
      className="w-full max-w-md h-[32rem] flex flex-col transition-all duration-300 hover:shadow-lg"
    >
      <CardHeader>
        <CardTitle className="text-lg font-semibold line-clamp-2">
          {memory.memory?.split("\n")[0]}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-grow overflow-hidden">
        {memory.media ? (
          <div className="relative w-full h-40 mb-4">
            <Image
              src={`data:image/png;base64,${memory.media}`}
              alt="Memory media"
              fill
              className="object-cover rounded-md"
            />
          </div>
        ) : (
          <div className="relative w-full h-40 mb-4">
            <Skeleton className="w-full h-full rounded-md" />
          </div>
        )}
        <div className="h-[calc(100%-10rem)] overflow-y-auto pr-2">
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
      </CardFooter>
    </Card>
  );
}
