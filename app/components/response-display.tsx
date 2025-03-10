"use client"

import { Card, CardContent } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { MarkdownRenderer } from "@/app/components/markdown-renderer"
import { useAutoScroll } from "@/app/hooks/useAutoScroll"

interface ResponseDisplayProps {
  content: string
}

export function ResponseDisplay({ content }: ResponseDisplayProps) {
  const { scrollRef, contentRef } = useAutoScroll(content)
  
  return (
    <Card className="w-full mt-3 flex-1 h-full overflow-hidden">
      <CardContent className="p-3 h-full pr-5">
        <ScrollArea ref={scrollRef} className="h-full w-full pr-2">
          <div ref={contentRef}>
            <MarkdownRenderer content={content} className="pr-4" />
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}