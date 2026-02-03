"use client";

import { useCallback, useEffect, useState } from "react";
import mammoth from "mammoth";

interface DocxPreviewProps {
  documentId: string;
  getDownloadUrl: (documentId: string, normalized: boolean) => Promise<string>;
  isAvailable: boolean;
}

interface PreviewState {
  status: "idle" | "loading" | "success" | "error";
  html: string | null;
  error: string | null;
  warnings: string[];
}

export function DocxPreview({
  documentId,
  getDownloadUrl,
  isAvailable,
}: DocxPreviewProps) {
  const [preview, setPreview] = useState<PreviewState>({
    status: "idle",
    html: null,
    error: null,
    warnings: [],
  });
  const [isExpanded, setIsExpanded] = useState(false);

  const loadPreview = useCallback(async () => {
    if (!isAvailable) {
      setPreview({
        status: "error",
        html: null,
        error: "Document not yet normalized. Please process the document first.",
        warnings: [],
      });
      return;
    }

    setPreview((prev) => ({ ...prev, status: "loading", error: null }));

    try {
      // Get signed URL for the normalized DOCX
      const url = await getDownloadUrl(documentId, true);

      // Fetch the DOCX file
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to fetch document: ${response.statusText}`);
      }

      // Convert response to ArrayBuffer
      const arrayBuffer = await response.arrayBuffer();

      // Convert DOCX to HTML using mammoth
      const result = await mammoth.convertToHtml({ arrayBuffer });

      setPreview({
        status: "success",
        html: result.value,
        error: null,
        warnings: result.messages
          .filter((m) => m.type === "warning")
          .map((m) => m.message),
      });
    } catch (err) {
      console.error("Failed to load DOCX preview:", err);
      setPreview({
        status: "error",
        html: null,
        error: err instanceof Error ? err.message : "Failed to load preview",
        warnings: [],
      });
    }
  }, [documentId, getDownloadUrl, isAvailable]);

  // Load preview when expanded
  useEffect(() => {
    if (isExpanded && preview.status === "idle") {
      loadPreview();
    }
  }, [isExpanded, preview.status, loadPreview]);

  return (
    <div className="bg-white shadow-sm rounded-lg overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors"
      >
        <h2 className="text-lg font-semibold text-gray-900">Document Preview</h2>
        <svg
          className={`w-5 h-5 text-gray-500 transition-transform ${isExpanded ? "rotate-180" : ""}`}
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

      {isExpanded && (
        <div className="px-6 pb-6 border-t border-gray-100">
          <div className="pt-4">
            {/* Loading State */}
            {preview.status === "loading" && (
              <div className="flex items-center justify-center py-12">
                <svg
                  className="animate-spin h-8 w-8 text-blue-600"
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
                <span className="ml-3 text-gray-600">Loading document preview...</span>
              </div>
            )}

            {/* Error State */}
            {preview.status === "error" && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-start">
                  <svg
                    className="w-5 h-5 text-red-600 mt-0.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <div className="ml-3">
                    <p className="text-sm text-red-700">{preview.error}</p>
                    <button
                      onClick={loadPreview}
                      className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
                    >
                      Try again
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Warnings */}
            {preview.warnings.length > 0 && (
              <div className="mb-4 bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                <p className="text-xs font-medium text-yellow-800 mb-1">
                  Conversion warnings:
                </p>
                <ul className="text-xs text-yellow-700 space-y-0.5">
                  {preview.warnings.slice(0, 5).map((warning, idx) => (
                    <li key={idx}>{warning}</li>
                  ))}
                  {preview.warnings.length > 5 && (
                    <li className="text-yellow-600">
                      +{preview.warnings.length - 5} more
                    </li>
                  )}
                </ul>
              </div>
            )}

            {/* Success - Rendered HTML */}
            {preview.status === "success" && preview.html && (
              <div
                className="prose prose-sm max-w-none overflow-auto max-h-[600px] border border-gray-200 rounded-lg p-4 bg-gray-50"
                dangerouslySetInnerHTML={{ __html: preview.html }}
              />
            )}

            {/* Idle state - not yet loaded */}
            {preview.status === "idle" && !isAvailable && (
              <div className="text-center py-8 text-gray-500">
                <p>Document preview is not available.</p>
                <p className="text-sm mt-1">
                  The document needs to be processed first.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
