"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createStatusStream, createStatusWatcher } from "../api";
import type { DocumentStatus, StatusUpdate } from "../types";

interface UseDocumentStatusOptions {
  documentId: string;
  autoStart?: boolean;
  force?: boolean;
  onComplete?: (status: DocumentStatus) => void;
  onError?: (error: string) => void;
}

interface UseDocumentStatusResult {
  status: DocumentStatus | null;
  progress: number;
  message: string | null;
  error: string | null;
  isConnected: boolean;
  isStarting: boolean;
  startProcessing: (forceReprocess?: boolean) => void;
  stopWatching: () => void;
}

export function useDocumentStatus({
  documentId,
  autoStart = false,
  force = false,
  onComplete,
  onError,
}: UseDocumentStatusOptions): UseDocumentStatusResult {
  const [status, setStatus] = useState<DocumentStatus | null>(null);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);

  const stopWatching = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    }
  }, []);

  const startProcessing = useCallback(async (forceReprocess?: boolean) => {
    // Close any existing connection
    stopWatching();

    // Reset state
    setProgress(0);
    setMessage(null);
    setError(null);
    setIsStarting(true);

    try {
      // Create new SSE connection (now async due to token retrieval)
      // Use forceReprocess argument if provided, otherwise fall back to hook option
      const shouldForce = forceReprocess ?? force;
      const eventSource = await createStatusStream(documentId, shouldForce);
      eventSourceRef.current = eventSource;

      // Set connected immediately after creating the EventSource
      // onopen may not fire reliably in all browsers
      setIsConnected(true);
      setIsStarting(false);

      eventSource.onopen = () => {
        // Ensure connected state is set (backup for browsers where it works)
        setIsConnected(true);
        setIsStarting(false);
      };

      eventSource.addEventListener("status", (event) => {
        const update: StatusUpdate = JSON.parse(event.data);
        setStatus(update.status);
        setProgress(update.progress);
        setMessage(update.message);

        if (update.status === "indexed") {
          onComplete?.(update.status);
          stopWatching();
        }
      });

      eventSource.addEventListener("error", (event) => {
        // @ts-expect-error - SSE error event may have data
        const data = event.data ? JSON.parse(event.data) : { error: "Connection error" };
        setError(data.error);
        onError?.(data.error);
        stopWatching();
        setIsStarting(false);
      });

      eventSource.onerror = () => {
        // Connection error
        if (eventSource.readyState === EventSource.CLOSED) {
          stopWatching();
          setIsStarting(false);
        }
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect");
      onError?.(err instanceof Error ? err.message : "Failed to connect");
      setIsStarting(false);
    }
  }, [documentId, force, onComplete, onError, stopWatching]);

  // Auto-start if requested
  useEffect(() => {
    if (autoStart) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- legitimate async operation triggered on mount
      startProcessing();
    }

    return () => {
      stopWatching();
    };
  }, [autoStart, startProcessing, stopWatching]);

  return {
    status,
    progress,
    message,
    error,
    isConnected,
    isStarting,
    startProcessing,
    stopWatching,
  };
}

interface UseStatusWatcherOptions {
  documentId: string;
  enabled?: boolean;
  onStatusChange?: (status: DocumentStatus) => void;
}

export function useStatusWatcher({
  documentId,
  enabled = true,
  onStatusChange,
}: UseStatusWatcherOptions) {
  const [status, setStatus] = useState<DocumentStatus | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled) return;

    let eventSource: EventSource | null = null;

    const setupWatcher = async () => {
      try {
        eventSource = await createStatusWatcher(documentId);
        eventSourceRef.current = eventSource;

        eventSource.onopen = () => {
          setIsConnected(true);
        };

        eventSource.addEventListener("status", (event) => {
          const data = JSON.parse(event.data);
          setStatus(data.status);
          onStatusChange?.(data.status);

          // Stop watching on terminal states
          if (data.status === "indexed" || data.status === "error") {
            eventSource?.close();
            setIsConnected(false);
          }
        });

        eventSource.onerror = () => {
          eventSource?.close();
          setIsConnected(false);
        };
      } catch {
        setIsConnected(false);
      }
    };

    setupWatcher();

    return () => {
      eventSource?.close();
    };
  }, [documentId, enabled, onStatusChange]);

  return { status, isConnected };
}
