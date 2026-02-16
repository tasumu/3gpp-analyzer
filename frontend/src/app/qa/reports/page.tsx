"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { AuthGuard } from "@/components/AuthGuard";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import {
  deleteQAReport,
  listQAReports,
  publishQAReport,
} from "@/lib/api";
import type { QAReportResponse } from "@/lib/types";
import { formatDate } from "@/lib/types";

export default function QAReportsPage() {
  const [reports, setReports] = useState<QAReportResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<Record<string, string>>({});
  const [previewLoading, setPreviewLoading] = useState(false);

  const loadReports = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await listQAReports();
      setReports(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const handlePublish = async (reportId: string, isPublic: boolean) => {
    try {
      const updated = await publishQAReport(reportId, isPublic);
      setReports((prev) =>
        prev.map((r) =>
          r.report_id === reportId ? { ...r, is_public: updated.is_public } : r
        )
      );
      toast.success(isPublic ? "Report published" : "Report unpublished");
    } catch {
      toast.error("Failed to update report visibility");
    }
  };

  const handleDelete = async (reportId: string) => {
    if (!confirm("Delete this report? This cannot be undone.")) return;
    try {
      await deleteQAReport(reportId);
      setReports((prev) => prev.filter((r) => r.report_id !== reportId));
      if (expandedId === reportId) setExpandedId(null);
      toast.success("Report deleted");
    } catch {
      toast.error("Failed to delete report");
    }
  };

  const handlePreview = async (report: QAReportResponse) => {
    if (expandedId === report.report_id) {
      setExpandedId(null);
      return;
    }

    setExpandedId(report.report_id);

    if (previewContent[report.report_id]) return;

    setPreviewLoading(true);
    try {
      const res = await fetch(report.download_url);
      if (!res.ok) throw new Error("Failed to fetch report");
      const text = await res.text();
      setPreviewContent((prev) => ({ ...prev, [report.report_id]: text }));
    } catch {
      toast.error("Failed to load preview");
      setExpandedId(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <AuthGuard>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">QA Reports</h1>
          <p className="text-sm text-gray-500 mt-1">
            Saved Q&A reports. Your reports and publicly shared reports are shown.
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error}
          </div>
        )}

        {isLoading && (
          <div className="text-center py-12 text-gray-500">Loading...</div>
        )}

        {!isLoading && !error && reports.length === 0 && (
          <div className="text-center py-12 border border-dashed border-gray-300 rounded-lg">
            <p className="text-gray-500">No reports found.</p>
            <p className="text-sm text-gray-400 mt-1">
              Save a report from the Q&A page to see it here.
            </p>
          </div>
        )}

        {!isLoading && reports.length > 0 && (
          <div className="space-y-3">
            {reports.map((report) => (
              <div
                key={report.report_id}
                className="bg-white border border-gray-200 rounded-lg shadow-sm"
              >
                <div className="flex items-start justify-between gap-4 p-4">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {report.question}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {formatDate(report.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => handlePublish(report.report_id, !report.is_public)}
                      className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors
                               focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
                      style={{ backgroundColor: report.is_public ? "#22c55e" : "#d1d5db" }}
                      role="switch"
                      aria-checked={report.is_public}
                      aria-label={report.is_public ? "Public: click to make private" : "Private: click to share with all users"}
                    >
                      <span
                        className="inline-block h-4 w-4 rounded-full bg-white shadow transition-transform"
                        style={{ transform: report.is_public ? "translateX(1.375rem)" : "translateX(0.25rem)" }}
                      />
                    </button>
                    <button
                      onClick={() => handlePreview(report)}
                      className={`px-3 py-1.5 text-sm border font-medium rounded-md ${
                        expandedId === report.report_id
                          ? "border-blue-500 text-blue-700 bg-blue-50"
                          : "border-gray-300 text-gray-700 hover:bg-gray-50"
                      }`}
                    >
                      {expandedId === report.report_id ? "Close" : "Preview"}
                    </button>
                    <a
                      href={report.download_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1.5 text-sm border border-green-600 text-green-700
                               font-medium rounded-md hover:bg-green-50"
                    >
                      Download
                    </a>
                    <button
                      onClick={() => handleDelete(report.report_id)}
                      className="px-3 py-1.5 text-sm border border-red-300 text-red-600
                               font-medium rounded-md hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                {expandedId === report.report_id && (
                  <div className="border-t border-gray-200 p-4">
                    {previewLoading && !previewContent[report.report_id] ? (
                      <div className="text-center py-4 text-gray-500 text-sm">Loading preview...</div>
                    ) : previewContent[report.report_id] ? (
                      <MarkdownRenderer content={previewContent[report.report_id]} showCopyButton={true} />
                    ) : null}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </AuthGuard>
  );
}
