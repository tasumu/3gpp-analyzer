"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { analyzeDocument, getDocumentSummary } from "@/lib/api";
import type { AnalysisLanguage, Document, DocumentSummary } from "@/lib/types";
import { languageLabels } from "@/lib/types";
import { DocumentSummaryCard } from "@/components/DocumentSummaryCard";

interface AnalysisPanelProps {
  document: Document;
  onAnalysisComplete?: () => void;
  language?: AnalysisLanguage;
  onLanguageChange?: (language: AnalysisLanguage) => void;
}

export function AnalysisPanel({
  document,
  onAnalysisComplete,
  language: externalLanguage,
  onLanguageChange,
}: AnalysisPanelProps) {
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [internalLanguage, setInternalLanguage] = useState<AnalysisLanguage>("ja");

  // Use external language if provided, otherwise use internal state
  const language = externalLanguage ?? internalLanguage;
  const setLanguage = (lang: AnalysisLanguage) => {
    if (onLanguageChange) {
      onLanguageChange(lang);
    } else {
      setInternalLanguage(lang);
    }
  };

  useEffect(() => {
    loadSummary();
  }, [document.id, language]);

  async function loadSummary() {
    try {
      setIsLoading(true);
      const result = await getDocumentSummary(document.id, language);
      setSummary(result);
    } catch (error) {
      console.error("Failed to load summary:", error);
      // Not showing error toast as the document might not have a summary yet
    } finally {
      setIsLoading(false);
    }
  }

  async function handleAnalyze(force = false) {
    if (isAnalyzing) return;

    try {
      setIsAnalyzing(true);
      const result = await analyzeDocument(document.id, {
        language,
        force,
      });
      setSummary(result);
      toast.success("Analysis completed");
      onAnalysisComplete?.();
    } catch (error) {
      console.error("Analysis failed:", error);
      toast.error("Analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  }

  const hasSummary = !!summary;

  return (
    <div className="space-y-6">
      {/* Description and Controls */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          Analyze this document to get a summary and key points.
        </p>
        <div className="flex items-center gap-4">
          {/* Language Selector */}
          <div className="flex items-center gap-2">
            <label
              htmlFor="analysis-language"
              className="text-sm font-medium text-gray-700"
            >
              Output Language:
            </label>
            <select
              id="analysis-language"
              value={language}
              onChange={(e) => setLanguage(e.target.value as AnalysisLanguage)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md
                       focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isAnalyzing}
            >
              {(Object.keys(languageLabels) as AnalysisLanguage[]).map((lang) => (
                <option key={lang} value={lang}>
                  {languageLabels[lang]}
                </option>
              ))}
            </select>
          </div>

          {/* Analyze Buttons */}
          <div className="flex gap-2">
            {hasSummary && (
              <button
                onClick={() => handleAnalyze(true)}
                disabled={isAnalyzing}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border
                         border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
              >
                Re-analyze
              </button>
            )}
            <button
              onClick={() => handleAnalyze(false)}
              disabled={isAnalyzing}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600
                       rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {isAnalyzing ? "Analyzing..." : hasSummary ? "Analyze" : "Start Analysis"}
            </button>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && !isAnalyzing && (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      )}

      {/* No Summary */}
      {!isLoading && !summary && !isAnalyzing && (
        <div className="text-center py-8 text-gray-500 border border-dashed rounded-lg">
          No analysis yet. Click &quot;Start Analysis&quot; to begin.
        </div>
      )}

      {/* Analyzing State */}
      {isAnalyzing && (
        <div className="text-center py-8 text-gray-500">
          <div className="animate-spin inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full mb-2" />
          <p>Analyzing document...</p>
        </div>
      )}

      {/* Summary Result */}
      {!isLoading && summary && !isAnalyzing && (
        <DocumentSummaryCard summary={summary} showCachedBadge={true} />
      )}
    </div>
  );
}
