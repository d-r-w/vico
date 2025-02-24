"use client"
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
  return (
    <Card className="w-full max-w-3xl mx-auto mt-4">
      <CardContent className="p-6">
        <ScrollArea className="h-[60vh] w-full pr-4">
          <div className="prose dark:prose-invert prose-sm sm:prose-base lg:prose-lg">
            <ReactMarkdown
              components={{
                h1: ({ ...props }) => <h1 className="text-2xl font-bold mb-4" {...props} />,
                h2: ({ ...props }) => <h2 className="text-xl font-semibold mb-3" {...props} />,
                h3: ({ ...props }) => <h3 className="text-lg font-medium mb-2" {...props} />,
                p: ({ ...props }) => <p className="mb-4" {...props} />,
                ul: ({ ...props }) => <ul className="list-disc pl-5 mb-4" {...props} />,
                ol: ({ ...props }) => <ol className="list-decimal pl-5 mb-4" {...props} />,
                li: ({ ...props }) => <li className="mb-1" {...props} />,
                a: ({ ...props }) => <a className="text-primary hover:underline" {...props} />,
                code: ({ inline, ...props }: CodeProps) =>
                  inline ? (
                    <code className="bg-muted text-muted-foreground px-1 py-0.5 rounded" {...props} />
                  ) : (
                    <pre className="bg-muted text-muted-foreground p-4 rounded-md overflow-x-auto">
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

