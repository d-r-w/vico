"use client"

import { useCallback, useEffect, useRef } from "react"

const AUTO_SCROLL_THRESHOLD_PX = 80

const getDistanceFromBottom = (viewport: HTMLDivElement) =>
  viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight

interface UseAutoScrollOptions {
  isStreaming: boolean
}

export function useAutoScroll(contentKey: string, { isStreaming }: UseAutoScrollOptions) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const shouldAutoScrollRef = useRef(true)

  const getViewport = useCallback(
    () => scrollRef.current?.querySelector<HTMLDivElement>("[data-radix-scroll-area-viewport]") ?? null,
    [],
  )

  const isNearBottom = useCallback((viewport: HTMLDivElement) => {
    return getDistanceFromBottom(viewport) <= AUTO_SCROLL_THRESHOLD_PX
  }, [])

  const scrollToBottom = useCallback(() => {
    const viewport = getViewport()
    if (!viewport) {
      return
    }

    viewport.scrollTop = viewport.scrollHeight
    shouldAutoScrollRef.current = true
  }, [getViewport])

  useEffect(() => {
    const viewport = getViewport()
    if (!viewport) {
      return
    }

    const updateAutoScrollState = () => {
      shouldAutoScrollRef.current = isNearBottom(viewport)
    }

    updateAutoScrollState()
    viewport.addEventListener("scroll", updateAutoScrollState, { passive: true })

    return () => {
      viewport.removeEventListener("scroll", updateAutoScrollState)
    }
  }, [getViewport, isNearBottom])

  useEffect(() => {
    if (!isStreaming && !shouldAutoScrollRef.current) {
      return
    }

    const frame = requestAnimationFrame(scrollToBottom)
    return () => cancelAnimationFrame(frame)
  }, [contentKey, isStreaming, scrollToBottom])

  return { scrollRef }
}