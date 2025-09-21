"use client"

import { memo } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

interface MarkdownRendererProps {
  content: string
  className?: string
}

const MarkdownRendererComponent = ({ content, className = "" }: MarkdownRendererProps) => {
  return (
    <div className={`prose prose-sm dark:prose-invert prose-zinc max-w-none ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Headings
          h1: ({ children }) => (
            <h1 className="text-xl font-bold mb-2 mt-4 first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-lg font-semibold mb-2 mt-3 first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-base font-medium mb-1 mt-2 first:mt-0">
              {children}
            </h3>
          ),

          // Code blocks
          code: ({ children, className, ...props }) => {
            const isInline = !className?.includes("language-");
            return isInline ? (
              <code
                className="bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded text-sm font-mono"
                {...props}
              >
                {children}
              </code>
            ) : (
              <code
                className="block bg-zinc-100 dark:bg-zinc-800 p-2 rounded text-sm font-mono overflow-x-auto"
                {...props}
              >
                {children}
              </code>
            );
          },

          // Lists
          ul: ({ children }) => (
            <ul className="list-disc list-inside my-2 space-y-1">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-inside my-2 space-y-1">
              {children}
            </ol>
          ),

          // Paragraphs
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,

          // Blockquotes
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-zinc-300 dark:border-zinc-700 pl-3 my-2 text-zinc-600 dark:text-zinc-400">
              {children}
            </blockquote>
          ),

          // Links
          a: ({ children, href }) => (
            <a
              href={href}
              className="text-blue-600 dark:text-blue-400 hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),

          // Tables
          table: ({ children }) => (
            <div className="overflow-x-auto my-2">
              <table className="min-w-full border-collapse border border-zinc-300 dark:border-zinc-700">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-zinc-300 dark:border-zinc-700 px-2 py-1 bg-zinc-50 dark:bg-zinc-800 font-medium text-left">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-zinc-300 dark:border-zinc-700 px-2 py-1">
              {children}
            </td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

export const MarkdownRenderer = memo(MarkdownRendererComponent) 