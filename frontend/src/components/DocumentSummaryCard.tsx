"use client";

import Link from "next/link";
import { useState } from "react";
import type { DocumentSummary } from "@/lib/types";

interface DocumentSummaryCardProps {
  summary: DocumentSummary;
  showCachedBadge?: boolean;
  customPrompt?: string | null;
}

export function DocumentSummaryCard({
  summary,
  showCachedBadge = true,
  customPrompt,
}: DocumentSummaryCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const summaryText = summary.summary || "";
  const showExpandButton = summaryText.length > 200;
  const displaySummary = isExpanded ? summaryText : summaryText.substring(0, 200);

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <Link
            href={`/documents/${summary.document_id}`}
            className="font-medium text-blue-600 hover:text-blue-800 hover:underline truncate block"
          >
            {summary.contribution_number}
          </Link>
          <p className="text-sm text-gray-600 truncate">{summary.title}</p>
          {summary.source && (
            <p className="text-xs text-gray-400 mt-1">{summary.source}</p>
          )}
          {customPrompt && (
            <p className="text-xs text-purple-600 mt-1 truncate" title={customPrompt}>
              <span className="font-medium">Custom Focus:</span> {customPrompt}
            </p>
          )}
        </div>
        {showCachedBadge && summary.from_cache && (
          <span className="ml-2 px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
            Cached
          </span>
        )}
      </div>

      <div className="mt-3">
        <p className="text-sm text-gray-700">
          {displaySummary}
          {showExpandButton && !isExpanded && "..."}
        </p>
        {showExpandButton && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs text-blue-600 hover:text-blue-800 mt-1"
          >
            {isExpanded ? "Show less" : "Show more"}
          </button>
        )}
      </div>

      {summary.key_points && summary.key_points.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-gray-500 mb-1">Key Points:</p>
          <ul className="text-xs text-gray-600 space-y-0.5">
            {summary.key_points
              .slice(0, isExpanded ? undefined : 3)
              .map((point, idx) => (
                <li key={idx} className="flex items-start">
                  <span className="text-blue-500 mr-1">•</span>
                  {point}
                </li>
              ))}
            {!isExpanded && summary.key_points.length > 3 && (
              <li className="text-gray-400">
                +{summary.key_points.length - 3} more
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
