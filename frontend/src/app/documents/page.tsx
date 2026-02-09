"use client";

import { useState, useCallback, useEffect } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DocumentList } from "@/components/DocumentList";
import { MeetingSelector } from "@/components/MeetingSelector";
import { useDocuments } from "@/lib/hooks/useDocuments";
import { batchProcessDocuments, batchDeleteDocuments } from "@/lib/api";
import type { DocumentStatus, DocumentType, BatchOperationResponse } from "@/lib/types";

const statusOptions: { value: DocumentStatus | ""; label: string }[] = [
  { value: "", label: "All Statuses" },
  { value: "metadata_only", label: "Metadata Only" },
  { value: "downloaded", label: "Downloaded" },
  { value: "normalized", label: "Normalized" },
  { value: "indexed", label: "Indexed" },
  { value: "error", label: "Error" },
];

const documentTypeOptions: { value: DocumentType | ""; label: string }[] = [
  { value: "", label: "All Types" },
  { value: "contribution", label: "Contribution" },
  { value: "other", label: "Other" },
];

export default function DocumentsPage() {
  const [meetingId, setMeetingId] = useState<string | null>(null);
  const [status, setStatus] = useState<DocumentStatus | "">("");
  const [documentType, setDocumentType] = useState<DocumentType | "">("");
  const [pathPrefix, setPathPrefix] = useState<string>("");
  const [searchText, setSearchText] = useState<string>("");
  const [debouncedSearchText, setDebouncedSearchText] = useState<string>("");
  const [page, setPage] = useState(1);

  // Debounce search text
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchText(searchText);
      setPage(1); // Reset to first page when search changes
    }, 500);

    return () => clearTimeout(timer);
  }, [searchText]);

  // Batch operation states
  const [batchLoading, setBatchLoading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string[] | null>(null);
  const [batchResult, setBatchResult] = useState<{
    type: "process" | "delete";
    result: BatchOperationResponse;
  } | null>(null);

  const { documents, total, isLoading, error, refresh } = useDocuments({
    meeting_id: meetingId || undefined,
    status: status || undefined,
    document_type: documentType || undefined,
    path_prefix: pathPrefix || undefined,
    search_text: debouncedSearchText || undefined,
    page,
    page_size: 50,
  });

  const totalPages = Math.ceil(total / 50);

  const handleBatchProcess = useCallback(async (ids: string[]) => {
    if (ids.length === 0) return;

    setBatchLoading(true);
    setBatchResult(null);

    try {
      const result = await batchProcessDocuments(ids, true);
      setBatchResult({ type: "process", result });
      refresh();
    } catch (err) {
      console.error("Batch process error:", err);
      setBatchResult({
        type: "process",
        result: {
          total: ids.length,
          success_count: 0,
          failed_count: ids.length,
          errors: { "error": err instanceof Error ? err.message : "Unknown error" },
        },
      });
    } finally {
      setBatchLoading(false);
    }
  }, [refresh]);

  const handleBatchDelete = useCallback((ids: string[]) => {
    if (ids.length === 0) return;
    setConfirmDelete(ids);
  }, []);

  const confirmBatchDelete = useCallback(async () => {
    if (!confirmDelete) return;

    setBatchLoading(true);
    setBatchResult(null);

    try {
      const result = await batchDeleteDocuments(confirmDelete);
      setBatchResult({ type: "delete", result });
      setConfirmDelete(null);
      refresh();
    } catch (err) {
      console.error("Batch delete error:", err);
      setBatchResult({
        type: "delete",
        result: {
          total: confirmDelete.length,
          success_count: 0,
          failed_count: confirmDelete.length,
          errors: { "error": err instanceof Error ? err.message : "Unknown error" },
        },
      });
      setConfirmDelete(null);
    } finally {
      setBatchLoading(false);
    }
  }, [confirmDelete, refresh]);

  return (
    <AuthGuard>
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
        <button
          onClick={refresh}
          className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        >
          <svg
            className="h-4 w-4 mr-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white shadow-sm rounded-lg p-4">
        <div className="flex flex-wrap gap-4 items-center">
          <MeetingSelector
            selectedMeetingId={meetingId}
            onSelect={setMeetingId}
          />

          <div className="flex items-center space-x-2">
            <label htmlFor="status-select" className="text-sm font-medium text-gray-700">
              Status:
            </label>
            <select
              id="status-select"
              value={status}
              onChange={(e) => setStatus(e.target.value as DocumentStatus | "")}
              className="block w-40 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            >
              {statusOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <label htmlFor="type-select" className="text-sm font-medium text-gray-700">
              Type:
            </label>
            <select
              id="type-select"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value as DocumentType | "")}
              className="block w-40 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            >
              {documentTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <label htmlFor="path-prefix" className="text-sm font-medium text-gray-700">
              Path:
            </label>
            <input
              id="path-prefix"
              type="text"
              value={pathPrefix}
              onChange={(e) => setPathPrefix(e.target.value)}
              placeholder="/Specs/latest/..."
              className="block w-48 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            />
          </div>

          <div className="flex items-center space-x-2">
            <label htmlFor="search-text" className="text-sm font-medium text-gray-700">
              Search:
            </label>
            <div className="relative">
              <input
                id="search-text"
                type="text"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder="Search by filename..."
                className="block w-64 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm pr-8"
              />
              {searchText && (
                <button
                  onClick={() => setSearchText("")}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-gray-600"
                  aria-label="Clear search"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          <div className="ml-auto text-sm text-gray-500">
            {total} documents
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-sm text-red-700">{error.message}</p>
        </div>
      )}

      {/* Batch operation result notification */}
      {batchResult && (
        <div
          className={`rounded-md p-4 ${
            batchResult.result.failed_count === 0
              ? "bg-green-50 border border-green-200"
              : batchResult.result.success_count === 0
                ? "bg-red-50 border border-red-200"
                : "bg-yellow-50 border border-yellow-200"
          }`}
        >
          <div className="flex justify-between items-start">
            <div>
              <h4
                className={`text-sm font-medium ${
                  batchResult.result.failed_count === 0
                    ? "text-green-800"
                    : batchResult.result.success_count === 0
                      ? "text-red-800"
                      : "text-yellow-800"
                }`}
              >
                {batchResult.type === "process" ? "Batch Process" : "Batch Delete"} Complete
              </h4>
              <p
                className={`text-sm mt-1 ${
                  batchResult.result.failed_count === 0
                    ? "text-green-700"
                    : batchResult.result.success_count === 0
                      ? "text-red-700"
                      : "text-yellow-700"
                }`}
              >
                {batchResult.result.success_count} of {batchResult.result.total} documents{" "}
                {batchResult.type === "process" ? "processed" : "deleted"} successfully.
                {batchResult.result.failed_count > 0 && (
                  <> {batchResult.result.failed_count} failed.</>
                )}
              </p>
              {Object.keys(batchResult.result.errors).length > 0 && (
                <ul className="mt-2 text-sm text-red-600 list-disc list-inside">
                  {Object.entries(batchResult.result.errors).slice(0, 5).map(([id, err]) => (
                    <li key={id}>
                      {id}: {err}
                    </li>
                  ))}
                  {Object.keys(batchResult.result.errors).length > 5 && (
                    <li>...and {Object.keys(batchResult.result.errors).length - 5} more errors</li>
                  )}
                </ul>
              )}
            </div>
            <button
              onClick={() => setBatchResult(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Document list */}
      <DocumentList
        documents={documents}
        isLoading={isLoading}
        onBatchProcess={handleBatchProcess}
        onBatchDelete={handleBatchDelete}
        batchLoading={batchLoading}
      />

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-gray-200 bg-white px-4 py-3 sm:px-6 rounded-lg shadow-sm">
          <div className="flex flex-1 justify-between sm:hidden">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="relative inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="relative ml-3 inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Next
            </button>
          </div>
          <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-gray-700">
                Showing <span className="font-medium">{(page - 1) * 50 + 1}</span> to{" "}
                <span className="font-medium">{Math.min(page * 50, total)}</span> of{" "}
                <span className="font-medium">{total}</span> results
              </p>
            </div>
            <div>
              <nav className="isolate inline-flex -space-x-px rounded-md shadow-sm">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="relative inline-flex items-center rounded-l-md px-2 py-2 text-gray-400 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 disabled:opacity-50"
                >
                  <span className="sr-only">Previous</span>
                  <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path
                      fillRule="evenodd"
                      d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
                <span className="relative inline-flex items-center px-4 py-2 text-sm font-semibold text-gray-900 ring-1 ring-inset ring-gray-300">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="relative inline-flex items-center rounded-r-md px-2 py-2 text-gray-400 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 disabled:opacity-50"
                >
                  <span className="sr-only">Next</span>
                  <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path
                      fillRule="evenodd"
                      d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
              </nav>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation dialog */}
      <ConfirmDialog
        open={confirmDelete !== null}
        title="Delete Documents"
        message={`Are you sure you want to delete ${confirmDelete?.length || 0} document(s)?\n\nThis will permanently remove all associated data including chunks and storage files. This action cannot be undone.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        destructive
        loading={batchLoading}
        onConfirm={confirmBatchDelete}
        onCancel={() => setConfirmDelete(null)}
      />
    </div>
    </AuthGuard>
  );
}
