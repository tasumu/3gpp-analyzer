"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { listAnalyses, getReviewSheetUrl } from "@/lib/api";
import type { AnalysisResult } from "@/lib/types";
import { analysisStatusColors, analysisStatusLabels } from "@/lib/types";

export default function AnalysisListPage() {
  const [analyses, setAnalyses] = useState<AnalysisResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadAnalyses() {
      try {
        setIsLoading(true);
        const response = await listAnalyses(50);
        setAnalyses(response.analyses);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load analyses");
      } finally {
        setIsLoading(false);
      }
    }
    loadAnalyses();
  }, []);

  return (
    <AuthGuard>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Analysis History</h1>
            <p className="text-sm text-gray-500 mt-1">
              View past document analyses and download review sheets.
            </p>
          </div>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="text-center py-12 text-gray-500">
            Loading analyses...
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && analyses.length === 0 && (
          <div className="text-center py-12 border border-dashed rounded-lg">
            <p className="text-gray-500">No analyses yet.</p>
            <Link
              href="/documents"
              className="mt-2 inline-block text-blue-600 hover:text-blue-800"
            >
              Go to documents to start analyzing
            </Link>
          </div>
        )}

        {/* Analysis list */}
        {!isLoading && analyses.length > 0 && (
          <div className="bg-white shadow-sm rounded-lg overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Contribution
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {analyses.map((analysis) => (
                  <tr key={analysis.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Link
                        href={`/documents/${analysis.document_id}`}
                        className="text-sm font-medium text-blue-600 hover:text-blue-800"
                      >
                        {analysis.contribution_number}
                      </Link>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {analysis.type === "single" ? "Single" : "Custom"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                          analysisStatusColors[analysis.status]
                        }`}
                      >
                        {analysisStatusLabels[analysis.status]}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(analysis.created_at).toLocaleString("ja-JP")}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <div className="flex gap-2">
                        <Link
                          href={`/documents/${analysis.document_id}`}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          View
                        </Link>
                        {analysis.status === "completed" && (
                          <a
                            href={getReviewSheetUrl(analysis.id)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-green-600 hover:text-green-800"
                          >
                            Download
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AuthGuard>
  );
}
