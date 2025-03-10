"use client"

import { useEffect, useRef } from "react"
import ReactMarkdown from "react-markdown"
import { Card, CardContent } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"

interface ResponseDisplayProps {
  content: string
}

interface CodeProps {
  inline?: boolean
  children?: React.ReactNode
  className?: string
}

export function ResponseDisplay({ content }: ResponseDisplayProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const observerRef = useRef<MutationObserver | null>(null)
  
  useEffect(() => {
    const scrollToBottom = () => {
      if (scrollAreaRef.current) {
        const scrollableArea = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]')
        if (scrollableArea) {
          scrollableArea.scrollTop = scrollableArea.scrollHeight
        }
      }
    }

    scrollToBottom()
    
    const timer = setTimeout(scrollToBottom, 50)
    
    if (contentRef.current && !observerRef.current) {
      observerRef.current = new MutationObserver(scrollToBottom)
      observerRef.current.observe(contentRef.current, { 
        childList: true, 
        subtree: true,
        characterData: true 
      })
    }
    
    return () => {
      clearTimeout(timer)
      if (observerRef.current) {
        observerRef.current.disconnect()
      }
    }
  }, [content])

  return (
    <Card className="w-full mt-3 flex-1 h-full overflow-hidden">
      <CardContent className="p-3 h-full pr-5">
        <ScrollArea ref={scrollAreaRef} className="h-full w-full pr-2">
          <div ref={contentRef} className="prose dark:prose-invert prose-sm sm:prose-base lg:prose-lg pr-4">
            <ReactMarkdown
              components={{
                h1: ({ ...props }) => <h1 className="text-2xl font-bold mb-2" {...props} />,
                h2: ({ ...props }) => <h2 className="text-xl font-semibold mb-2" {...props} />,
                h3: ({ ...props }) => <h3 className="text-lg font-medium mb-1" {...props} />,
                p: ({ ...props }) => <p className="mb-2" {...props} />,
                ul: ({ ...props }) => <ul className="list-disc pl-4 mb-2" {...props} />,
                ol: ({ ...props }) => <ol className="list-decimal pl-4 mb-2" {...props} />,
                li: ({ ...props }) => <li className="mb-0.5" {...props} />,
                a: ({ ...props }) => <a className="text-primary hover:underline" {...props} />,
                code: ({ inline, ...props }: CodeProps) =>
                  inline ? (
                    <code className="bg-muted text-muted-foreground px-0.5 py-0.5 rounded" {...props} />
                  ) : (
                    <pre className="bg-muted text-muted-foreground p-2 rounded-md overflow-x-auto">
                      <code {...props} />
                    </pre>
                  ),
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}