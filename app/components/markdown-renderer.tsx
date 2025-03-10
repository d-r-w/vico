"use client"

import ReactMarkdown from "react-markdown"

interface MarkdownRendererProps {
  content: string
  className?: string
}

interface CodeProps {
  inline?: boolean
  children?: React.ReactNode
  className?: string
}

export function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  return (
    <div className={`prose dark:prose-invert prose-sm sm:prose-base lg:prose-lg ${className}`}>
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
  )
} 