import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import { CalendarIcon } from "lucide-react";
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
      </CardFooter>
    </Card>
  );
}
