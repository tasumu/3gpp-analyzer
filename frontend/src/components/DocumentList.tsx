"use client";

import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { DocumentStatusBadge } from "./DocumentStatusBadge";
import type { Document } from "@/lib/types";
import { formatDate, formatFileSize, isProcessing } from "@/lib/types";

interface DocumentListProps {
  documents: Document[];
  isLoading?: boolean;
  onBatchProcess?: (ids: string[]) => void;
  onBatchDelete?: (ids: string[]) => void;
  batchLoading?: boolean;
}

export function DocumentList({
  documents,
  isLoading,
  onBatchProcess,
  onBatchDelete,
  batchLoading = false,
}: DocumentListProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Clear selection when documents change
  useEffect(() => {
    setSelectedIds(new Set());
  }, [documents]);

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === documents.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(documents.map((d) => d.id)));
    }
  }, [documents, selectedIds.size]);

  const toggleSelect = useCallback((id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-16 bg-gray-200 rounded" />
        ))}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-12">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-gray-900">No documents</h3>
        <p className="mt-1 text-sm text-gray-500">
          No documents found matching your filters.
        </p>
      </div>
    );
  }

  const hasSelection = selectedIds.size > 0;
  const allSelected = selectedIds.size === documents.length && documents.length > 0;

  return (
    <div className="space-y-4">
      {/* Batch Action Toolbar */}
      {hasSelection && (
        <div className="bg-primary-50 border border-primary-200 rounded-lg p-3 flex items-center justify-between">
          <span className="text-sm text-primary-700 font-medium">
            {selectedIds.size} document{selectedIds.size !== 1 ? "s" : ""} selected
          </span>
          <div className="flex items-center gap-2">
            {onBatchProcess && (
              <button
                onClick={() => onBatchProcess(Array.from(selectedIds))}
                disabled={batchLoading}
                className="px-3 py-1.5 text-sm font-medium bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Process Selected
              </button>
            )}
            {onBatchDelete && (
              <button
                onClick={() => onBatchDelete(Array.from(selectedIds))}
                disabled={batchLoading}
                className="px-3 py-1.5 text-sm font-medium bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Delete Selected
              </button>
            )}
            <button
              onClick={clearSelection}
              disabled={batchLoading}
              className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 disabled:opacity-50"
            >
              Clear
            </button>
          </div>
        </div>
      )}

      <div className="bg-white shadow-sm rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 w-10">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500 cursor-pointer"
                />
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                ID / Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Title
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Meeting
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Size
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Updated
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {documents.map((doc) => (
              <tr
                key={doc.id}
                className={`hover:bg-gray-50 ${
                  selectedIds.has(doc.id) ? "bg-primary-50" : ""
                }`}
              >
                <td className="px-4 py-4 whitespace-nowrap">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(doc.id)}
                    onClick={(e) => toggleSelect(doc.id, e)}
                    onChange={() => {}}
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500 cursor-pointer"
                  />
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <Link
                    href={`/documents/${doc.id}`}
                    className="text-primary-600 hover:text-primary-900 font-medium"
                  >
                    {doc.contribution_number || doc.filename}
                  </Link>
                  {doc.document_type !== "contribution" && (
                    <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                      {doc.document_type}
                    </span>
                  )}
                </td>
                <td className="px-6 py-4">
                  <div className="text-sm text-gray-900 truncate max-w-md">
                    {doc.title || doc.filename}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {doc.meeting_name || "-"}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <DocumentStatusBadge status={doc.status} />
                    {isProcessing(doc.status) && (
                      <svg
                        className="ml-2 h-4 w-4 text-primary-600 animate-spin"
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
                    )}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatFileSize(doc.file_size_bytes)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatDate(doc.updated_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
