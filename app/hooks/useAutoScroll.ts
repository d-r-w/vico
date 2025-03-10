"use client"

import { useEffect, useRef } from "react"

export function useAutoScroll(content: string) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const observerRef = useRef<MutationObserver | null>(null)
  
  useEffect(() => {
    const scrollToBottom = () => {
      if (scrollRef.current) {
        const scrollableArea = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]')
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
        observerRef.current = null
      }
    }
  }, [content])

  return { scrollRef, contentRef }
} 