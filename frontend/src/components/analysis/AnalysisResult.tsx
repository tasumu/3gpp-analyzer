"use client";

import { useState } from "react";
import { getReviewSheetUrl } from "@/lib/api";
import type {
  AnalysisResult,
  SingleAnalysis,
  Change,
  Issue,
  Evidence,
  changeTypeLabels,
  changeTypeColors,
  severityLabels,
  severityColors,
} from "@/lib/types";
import { EvidenceCitation } from "./EvidenceCitation";

interface AnalysisResultDisplayProps {
  analysis: AnalysisResult;
}

export function AnalysisResultDisplay({ analysis }: AnalysisResultDisplayProps) {
  const [expandedSection, setExpandedSection] = useState<string | null>("summary");

  if (analysis.status !== "completed" || !analysis.result) {
    return (
      <div className="text-center py-8 text-gray-500">
        Analysis not completed yet.
      </div>
    );
  }

  // Type guard for single analysis
  const isSingleAnalysis = analysis.type === "single";
  const rawResult = analysis.result as SingleAnalysis;

  // Ensure arrays are defined (defensive coding for Firestore data)
  const result = {
    ...rawResult,
    changes: rawResult.changes || [],
    issues: rawResult.issues || [],
    evidences: rawResult.evidences || [],
  };

  const downloadUrl = getReviewSheetUrl(analysis.id);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b">
        <div>
          <span className="text-sm text-gray-500">
            Analyzed: {new Date(analysis.created_at).toLocaleString("ja-JP")}
          </span>
        </div>
        <a
          href={downloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50
                   rounded-md hover:bg-blue-100 flex items-center gap-1"
        >
          <DownloadIcon className="w-4 h-4" />
          Download Review Sheet
        </a>
      </div>

      {/* Summary Section */}
      <Section
        title="Summary"
        isExpanded={expandedSection === "summary"}
        onToggle={() =>
          setExpandedSection(expandedSection === "summary" ? null : "summary")
        }
      >
        <p className="text-gray-700 leading-relaxed">{result.summary}</p>
      </Section>

      {/* Changes Section */}
      <Section
        title={`Proposed Changes (${result.changes.length})`}
        isExpanded={expandedSection === "changes"}
        onToggle={() =>
          setExpandedSection(expandedSection === "changes" ? null : "changes")
        }
      >
        {result.changes.length === 0 ? (
          <p className="text-gray-500 italic">No changes identified.</p>
        ) : (
          <div className="space-y-3">
            {result.changes.map((change, index) => (
              <ChangeItem key={index} change={change} />
            ))}
          </div>
        )}
      </Section>

      {/* Issues Section */}
      <Section
        title={`Issues & Discussion Points (${result.issues.length})`}
        isExpanded={expandedSection === "issues"}
        onToggle={() =>
          setExpandedSection(expandedSection === "issues" ? null : "issues")
        }
      >
        {result.issues.length === 0 ? (
          <p className="text-gray-500 italic">No issues identified.</p>
        ) : (
          <div className="space-y-3">
            {result.issues.map((issue, index) => (
              <IssueItem key={index} issue={issue} />
            ))}
          </div>
        )}
      </Section>

      {/* Evidence Section */}
      <Section
        title={`Evidence & Citations (${result.evidences.length})`}
        isExpanded={expandedSection === "evidence"}
        onToggle={() =>
          setExpandedSection(expandedSection === "evidence" ? null : "evidence")
        }
      >
        {result.evidences.length === 0 ? (
          <p className="text-gray-500 italic">No evidence cited.</p>
        ) : (
          <div className="space-y-2">
            {result.evidences.slice(0, 10).map((evidence, index) => (
              <EvidenceCitation key={index} evidence={evidence} />
            ))}
            {result.evidences.length > 10 && (
              <p className="text-sm text-gray-500">
                ...and {result.evidences.length - 10} more citations
              </p>
            )}
          </div>
        )}
      </Section>
    </div>
  );
}

// Section component
interface SectionProps {
  title: string;
  isExpanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

function Section({ title, isExpanded, onToggle, children }: SectionProps) {
  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between bg-gray-50
                 hover:bg-gray-100 transition-colors"
      >
        <span className="font-medium text-gray-900">{title}</span>
        <ChevronIcon className={`w-5 h-5 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
      </button>
      {isExpanded && <div className="p-4 bg-white">{children}</div>}
    </div>
  );
}

// Change item component
interface ChangeItemProps {
  change: Change;
}

function ChangeItem({ change }: ChangeItemProps) {
  const typeColors: Record<string, string> = {
    addition: "bg-green-100 text-green-800",
    modification: "bg-yellow-100 text-yellow-800",
    deletion: "bg-red-100 text-red-800",
  };

  const typeLabels: Record<string, string> = {
    addition: "Addition",
    modification: "Modification",
    deletion: "Deletion",
  };

  return (
    <div className="p-3 bg-gray-50 rounded-lg">
      <div className="flex items-start gap-2">
        <span
          className={`px-2 py-0.5 text-xs font-medium rounded ${
            typeColors[change.type] || "bg-gray-100 text-gray-800"
          }`}
        >
          {typeLabels[change.type] || change.type}
        </span>
        {change.clause && (
          <span className="text-xs text-gray-500">Clause {change.clause}</span>
        )}
      </div>
      <p className="mt-2 text-sm text-gray-700">{change.description}</p>
    </div>
  );
}

// Issue item component
interface IssueItemProps {
  issue: Issue;
}

function IssueItem({ issue }: IssueItemProps) {
  const severityColors: Record<string, string> = {
    high: "bg-red-100 text-red-800",
    medium: "bg-yellow-100 text-yellow-800",
    low: "bg-blue-100 text-blue-800",
  };

  const severityLabels: Record<string, string> = {
    high: "High",
    medium: "Medium",
    low: "Low",
  };

  return (
    <div className="p-3 bg-gray-50 rounded-lg">
      <div className="flex items-start gap-2">
        <span
          className={`px-2 py-0.5 text-xs font-medium rounded ${
            severityColors[issue.severity] || "bg-gray-100 text-gray-800"
          }`}
        >
          {severityLabels[issue.severity] || issue.severity}
        </span>
      </div>
      <p className="mt-2 text-sm text-gray-700">{issue.description}</p>
    </div>
  );
}

// Icons
function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
      />
    </svg>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 9l-7 7-7-7"
      />
    </svg>
  );
}
