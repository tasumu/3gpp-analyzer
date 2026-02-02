"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AnalysisPanel } from "@/components/analysis";
import { AuthGuard } from "@/components/AuthGuard";
import { DocumentStatusBadge } from "@/components/DocumentStatusBadge";
import { ProcessingProgress } from "@/components/ProcessingProgress";
import { deleteDocument, getDocument, getDownloadUrl } from "@/lib/api";
import type { Document } from "@/lib/types";
import { formatDate, formatFileSize } from "@/lib/types";

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  const [document, setDocument] = useState<Document | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchDocument = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const doc = await getDocument(documentId);
      setDocument(doc);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load document");
    } finally {
      setIsLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    fetchDocument();
  }, [fetchDocument]);

  const handleDownload = async (normalized: boolean) => {
    try {
      const url = await getDownloadUrl(documentId, normalized);
      window.open(url, "_blank");
    } catch {
      alert("Failed to get download URL");
    }
  };

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this document?")) {
      return;
    }

    setIsDeleting(true);
    try {
      await deleteDocument(documentId);
      router.push("/documents");
    } catch {
      alert("Failed to delete document");
      setIsDeleting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-gray-200 rounded w-1/3" />
        <div className="h-64 bg-gray-200 rounded" />
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">Document not found</h2>
        <p className="text-gray-500 mt-2">{error}</p>
        <Link
          href="/documents"
          className="mt-4 inline-flex items-center text-primary-600 hover:text-primary-900"
        >
          Back to documents
        </Link>
      </div>
    );
  }

  return (
    <AuthGuard>
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link
            href="/documents"
            className="text-sm text-gray-500 hover:text-gray-700 flex items-center mb-2"
          >
            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to documents
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">{document.contribution_number}</h1>
          {document.title && (
            <p className="text-lg text-gray-600 mt-1">{document.title}</p>
          )}
        </div>
        <DocumentStatusBadge status={document.status} className="text-sm" />
      </div>

      {/* Document info */}
      <div className="bg-white shadow-sm rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Document Information</h2>
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <dt className="text-sm font-medium text-gray-500">Contribution Number</dt>
            <dd className="mt-1 text-sm text-gray-900">{document.contribution_number}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Meeting</dt>
            <dd className="mt-1 text-sm text-gray-900">{document.meeting_name || "-"}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Filename</dt>
            <dd className="mt-1 text-sm text-gray-900">{document.filename}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">File Size</dt>
            <dd className="mt-1 text-sm text-gray-900">{formatFileSize(document.file_size_bytes)}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Chunks</dt>
            <dd className="mt-1 text-sm text-gray-900">{document.chunk_count}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Last Updated</dt>
            <dd className="mt-1 text-sm text-gray-900">{formatDate(document.updated_at)}</dd>
          </div>
        </dl>

        {document.error_message && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{document.error_message}</p>
          </div>
        )}
      </div>

      {/* Processing */}
      <div className="bg-white shadow-sm rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Processing</h2>
        <ProcessingProgress
          documentId={document.id}
          currentStatus={document.status}
          chunkCount={document.chunk_count}
          onComplete={fetchDocument}
        />
      </div>

      {/* Analysis (only for indexed documents) */}
      {document.status === "indexed" && (
        <div className="bg-white shadow-sm rounded-lg p-6">
          <AnalysisPanel document={document} onAnalysisComplete={fetchDocument} />
        </div>
      )}

      {/* Actions */}
      <div className="bg-white shadow-sm rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Actions</h2>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => handleDownload(false)}
            disabled={document.status === "metadata_only" || document.status === "downloading"}
            className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            title={document.status === "metadata_only" || document.status === "downloading" ? "File not yet downloaded" : undefined}
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download Original
          </button>
          <button
            onClick={() => handleDownload(true)}
            disabled={!["normalized", "chunking", "chunked", "indexing", "indexed"].includes(document.status)}
            className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            title={!["normalized", "chunking", "chunked", "indexing", "indexed"].includes(document.status) ? "Document not yet normalized" : undefined}
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download DOCX
          </button>
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="inline-flex items-center px-4 py-2 border border-red-300 shadow-sm text-sm font-medium rounded-md text-red-700 bg-white hover:bg-red-50 disabled:opacity-50"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            {isDeleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>
    </div>
    </AuthGuard>
  );
}
