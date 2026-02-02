"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { analyzeDocument, getDocumentAnalyses } from "@/lib/api";
import type { AnalysisLanguage, AnalysisResult, Document } from "@/lib/types";
import { languageLabels } from "@/lib/types";
import { AnalysisResultDisplay } from "./AnalysisResult";
import { AnalysisProgress } from "./AnalysisProgress";

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
  const [analyses, setAnalyses] = useState<AnalysisResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [currentAnalysisId, setCurrentAnalysisId] = useState<string | null>(null);
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
    loadAnalyses();
  }, [document.id]);

  async function loadAnalyses() {
    try {
      setIsLoading(true);
      const response = await getDocumentAnalyses(document.id);
      setAnalyses(response.analyses);
    } catch (error) {
      console.error("Failed to load analyses:", error);
      toast.error("Failed to load analyses");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleAnalyze(force = false) {
    if (isAnalyzing) return;

    try {
      setIsAnalyzing(true);
      const result = await analyzeDocument(document.id, force, { language });
      setCurrentAnalysisId(result.id);

      if (result.status === "completed") {
        toast.success("Analysis completed");
        await loadAnalyses();
        setIsAnalyzing(false);
        setCurrentAnalysisId(null);
        onAnalysisComplete?.();
      }
    } catch (error) {
      console.error("Analysis failed:", error);
      toast.error("Analysis failed");
      setIsAnalyzing(false);
      setCurrentAnalysisId(null);
    }
  }

  function handleAnalysisComplete() {
    setIsAnalyzing(false);
    setCurrentAnalysisId(null);
    loadAnalyses();
    onAnalysisComplete?.();
  }

  function handleAnalysisError(error: string) {
    toast.error(`Analysis failed: ${error}`);
    setIsAnalyzing(false);
    setCurrentAnalysisId(null);
  }

  const latestCompletedAnalysis = analyses.find((a) => a.status === "completed");
  const hasCompletedAnalysis = !!latestCompletedAnalysis;

  return (
    <div className="space-y-6">
      {/* Description and Controls */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          Analyze this document to extract key points, changes, and issues.
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
            {hasCompletedAnalysis && (
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
              {isAnalyzing ? "Analyzing..." : hasCompletedAnalysis ? "Analyze" : "Start Analysis"}
            </button>
          </div>
        </div>
      </div>

      {/* Analysis Progress */}
      {isAnalyzing && currentAnalysisId && (
        <AnalysisProgress
          analysisId={currentAnalysisId}
          onComplete={handleAnalysisComplete}
          onError={handleAnalysisError}
        />
      )}

      {/* Loading State */}
      {isLoading && !isAnalyzing && (
        <div className="text-center py-8 text-gray-500">Loading analyses...</div>
      )}

      {/* No Analyses */}
      {!isLoading && analyses.length === 0 && !isAnalyzing && (
        <div className="text-center py-8 text-gray-500 border border-dashed rounded-lg">
          No analyses yet. Click &quot;Start Analysis&quot; to begin.
        </div>
      )}

      {/* Analysis Results */}
      {!isLoading && latestCompletedAnalysis && (
        <AnalysisResultDisplay analysis={latestCompletedAnalysis} />
      )}

      {/* Previous Analyses */}
      {analyses.length > 1 && (
        <div className="border-t pt-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Previous Analyses</h4>
          <div className="space-y-2">
            {analyses.slice(1).map((analysis) => (
              <div
                key={analysis.id}
                className="text-sm text-gray-500 flex items-center justify-between
                         p-2 bg-gray-50 rounded"
              >
                <span>
                  {new Date(analysis.created_at).toLocaleString("ja-JP")} -{" "}
                  {analysis.status}
                </span>
                <span className="text-xs text-gray-400">v{analysis.strategy_version}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
