"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useDocumentStatus } from "@/lib/hooks/useDocumentStatus";
import { getDocumentChunks } from "@/lib/api";
import type { Chunk, DocumentStatus } from "@/lib/types";
import { isProcessable } from "@/lib/types";
import { ChunkList } from "./ChunkList";

interface ProcessingProgressProps {
  documentId: string;
  currentStatus: DocumentStatus;
  chunkCount: number;
  onComplete?: () => void;
}

export function ProcessingProgress({
  documentId,
  currentStatus,
  chunkCount,
  onComplete,
}: ProcessingProgressProps) {
  const [isChunkSectionExpanded, setIsChunkSectionExpanded] = useState(false);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [isLoadingChunks, setIsLoadingChunks] = useState(false);
  const [chunksError, setChunksError] = useState<string | null>(null);
  const toastShownRef = useRef(false);

  const showCompletionToast = useCallback((finalStatus: DocumentStatus) => {
    if (toastShownRef.current) return;

    if (finalStatus === "indexed") {
      toast.success("Processing complete", {
        description: "Document has been successfully indexed.",
      });
      toastShownRef.current = true;
    } else if (finalStatus === "error") {
      toast.error("Processing failed", {
        description: "An error occurred during processing.",
      });
      toastShownRef.current = true;
    }
  }, []);

  const {
    status,
    progress,
    message,
    error,
    isConnected,
    isStarting,
    startProcessing,
  } = useDocumentStatus({
    documentId,
    onComplete: (finalStatus) => {
      showCompletionToast(finalStatus);
      onComplete?.();
    },
  });

  // Reset toast flag when starting a new processing
  useEffect(() => {
    if (isConnected) {
      toastShownRef.current = false;
    }
  }, [isConnected]);

  const loadChunks = useCallback(async () => {
    setIsLoadingChunks(true);
    setChunksError(null);

    try {
      const response = await getDocumentChunks(documentId);
      setChunks(response.chunks);
    } catch (err) {
      setChunksError(
        err instanceof Error ? err.message : "Failed to load chunks",
      );
    } finally {
      setIsLoadingChunks(false);
    }
  }, [documentId]);

  useEffect(() => {
    if (isChunkSectionExpanded && chunks.length === 0 && !isLoadingChunks) {
      loadChunks();
    }
  }, [isChunkSectionExpanded, chunks.length, isLoadingChunks, loadChunks]);

  const canProcess = isProcessable(currentStatus);
  const displayStatus = status || currentStatus;
  const displayProgress = progress * 100;
  const isIndexed = displayStatus === "indexed";

  return (
    <div className="space-y-4">
      {/* Progress bar - show only when processing */}
      {isConnected && (
        <div className="w-full">
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>{message || "Processing..."}</span>
            <span>{displayProgress.toFixed(0)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-primary-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${displayProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Process button */}
      {canProcess && !isConnected && !isStarting && (
        <button
          onClick={() => startProcessing(currentStatus === "indexed")}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        >
          <svg
            className="w-4 h-4 mr-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          {currentStatus === "indexed" ? "Reprocess Document" : "Process Document"}
        </button>
      )}

      {/* Processing indicator */}
      {(isStarting || isConnected) && (
        <div className="flex items-center text-sm text-gray-600">
          <svg
            className="animate-spin -ml-1 mr-2 h-4 w-4 text-primary-600"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          {isStarting ? "Starting..." : "Processing..."}
        </div>
      )}

      {/* Indexed Status - Collapsible Chunk Section */}
      {isIndexed && chunkCount > 0 && (
        <div className="border border-green-200 rounded-lg overflow-hidden">
          <button
            onClick={() => setIsChunkSectionExpanded(!isChunkSectionExpanded)}
            className="w-full flex items-center justify-between px-4 py-3 bg-green-50 hover:bg-green-100 transition-colors"
          >
            <div className="flex items-center gap-2">
              <svg
                className="w-5 h-5 text-green-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="text-sm font-medium text-green-800">
                Processing complete - {chunkCount} chunks indexed
              </span>
            </div>
            <svg
              className={`w-5 h-5 text-green-600 transition-transform ${isChunkSectionExpanded ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>

          {isChunkSectionExpanded && (
            <div className="p-4 bg-white border-t border-green-200">
              {chunksError ? (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                  <p className="text-sm text-red-700">{chunksError}</p>
                  <button
                    onClick={loadChunks}
                    className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
                  >
                    Retry
                  </button>
                </div>
              ) : (
                <ChunkList chunks={chunks} isLoading={isLoadingChunks} />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
