"use client";

import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Hash, X } from "lucide-react";
import type { Tag } from "@/app/types";
import { cn } from "@/lib/utils";

interface TagSidebarProps {
  tags: Tag[];
}

export function TagSidebar({ tags }: TagSidebarProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const activeTagId = searchParams.get("tag");

  const handleTagClick = (tagId: number) => {
    const params = new URLSearchParams(searchParams);
    if (activeTagId === tagId.toString()) {
      params.delete("tag");
    } else {
      params.set("tag", tagId.toString());
    }
    router.push(`${pathname}?${params.toString()}`);
  };

  return (
    <div className="h-full flex flex-col border-r bg-muted/10">
      <div className="p-4 border-b flex items-center justify-between">
        <h2 className="font-semibold text-sm uppercase tracking-wider text-muted-foreground">Tags</h2>
        {activeTagId && (
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-6 w-6" 
            onClick={() => {
               const params = new URLSearchParams(searchParams);
               params.delete("tag");
               router.push(`${pathname}?${params.toString()}`);
            }}
            title="Clear filter"
          >
            <X className="h-3 w-3" />
          </Button>
        )}
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {tags.map((tag) => (
            <Button
              key={tag.id}
              variant={activeTagId === tag.id.toString() ? "secondary" : "ghost"}
              className={cn(
                "w-full justify-start text-sm font-normal",
                activeTagId === tag.id.toString() && "bg-secondary font-medium"
              )}
              onClick={() => handleTagClick(tag.id)}
            >
              <Hash className="mr-2 h-3 w-3 opacity-50" />
              {tag.label}
            </Button>
          ))}
          {tags.length === 0 && (
            <div className="p-4 text-xs text-muted-foreground text-center">
              No tags found
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}


