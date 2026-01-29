"use client";

import { useDocumentStatus } from "@/lib/hooks/useDocumentStatus";
import type { DocumentStatus } from "@/lib/types";
import { isProcessable } from "@/lib/types";

interface ProcessingProgressProps {
  documentId: string;
  currentStatus: DocumentStatus;
  onComplete?: () => void;
}

export function ProcessingProgress({
  documentId,
  currentStatus,
  onComplete,
}: ProcessingProgressProps) {
  const {
    status,
    progress,
    message,
    error,
    isConnected,
    startProcessing,
  } = useDocumentStatus({
    documentId,
    onComplete: onComplete ? () => onComplete() : undefined,
  });

  const canProcess = isProcessable(currentStatus);
  const displayStatus = status || currentStatus;
  const displayProgress = progress * 100;

  return (
    <div className="space-y-3">
      {/* Progress bar */}
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
      {canProcess && !isConnected && (
        <button
          onClick={startProcessing}
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
          Process Document
        </button>
      )}

      {/* Processing indicator */}
      {isConnected && (
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
          Processing...
        </div>
      )}
    </div>
  );
}
