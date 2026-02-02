"use client";

import { useState } from "react";
import type { Evidence } from "@/lib/types";

interface EvidenceCitationProps {
  evidence: Evidence;
}

export function EvidenceCitation({ evidence }: EvidenceCitationProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const citation = [
    evidence.contribution_number,
    evidence.clause_number ? `Clause ${evidence.clause_number}` : null,
    evidence.page_number ? `Page ${evidence.page_number}` : null,
  ]
    .filter(Boolean)
    .join(", ");

  const previewLength = 150;
  const hasMore = evidence.content.length > previewLength;
  const preview = hasMore
    ? evidence.content.substring(0, previewLength) + "..."
    : evidence.content;

  return (
    <div className="border-l-2 border-gray-300 pl-3 py-1">
      <div className="text-xs text-gray-500 font-medium">{citation}</div>
      <div className="mt-1 text-sm text-gray-700">
        {isExpanded ? evidence.content : preview}
      </div>
      {hasMore && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-xs text-blue-600 hover:text-blue-800 mt-1"
        >
          {isExpanded ? "Show less" : "Show more"}
        </button>
      )}
      <div className="mt-1 text-xs text-gray-400">
        Relevance: {Math.round(evidence.relevance_score * 100)}%
      </div>
    </div>
  );
}
