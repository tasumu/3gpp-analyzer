"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { AuthGuard } from "@/components/AuthGuard";
import { DocumentSummaryCard } from "@/components/DocumentSummaryCard";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import { SavedPromptSelector } from "@/components/meeting/SavedPromptSelector";
import {
  getMultipleMeetingInfo,
  createMultiMeetingSummarizeStream,
} from "@/lib/api";
import type {
  AnalysisLanguage,
  MultiMeetingInfo,
  MultiMeetingSummary,
  MeetingSummary,
} from "@/lib/types";
import { languageLabels } from "@/lib/types";

interface MultiMeetingSummaryProgress {
  currentMeeting: number;
  totalMeetings: number;
  currentMeetingId: string | null;
  stage: string;
  documentsProcessed?: number;
  totalDocuments?: number;
}

export default function MultiMeetingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const meetingIds = useMemo(
    () => searchParams.get("ids")?.split(",").filter(Boolean) || [],
    [searchParams]
  );

  const [meetingInfo, setMeetingInfo] = useState<MultiMeetingInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Summarize state
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [summaryProgress, setSummaryProgress] = useState<MultiMeetingSummaryProgress | null>(null);
  const [currentSummary, setCurrentSummary] = useState<MultiMeetingSummary | null>(null);

  // Settings
  const [analysisPrompt, setAnalysisPrompt] = useState("");
  const [language, setLanguage] = useState<AnalysisLanguage>("ja");
  const [force, setForce] = useState(false);
  const [showAllDocuments, setShowAllDocuments] = useState(false);

  const loadMeetingData = useCallback(async () => {
    if (meetingIds.length < 2) {
      setError("At least 2 meeting IDs required");
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      const info = await getMultipleMeetingInfo(meetingIds);
      setMeetingInfo(info);
    } catch (err) {
      console.error("Failed to load meeting data:", err);
      setError(err instanceof Error ? err.message : "Failed to load meetings");
    } finally {
      setIsLoading(false);
    }
  }, [meetingIds]);

  useEffect(() => {
    loadMeetingData();
  }, [loadMeetingData]);

  async function handleSummarize() {
    if (isSummarizing) return;

    setIsSummarizing(true);
    setSummaryProgress(null);

    try {
      const eventSource = await createMultiMeetingSummarizeStream(meetingIds, {
        analysisPrompt: analysisPrompt || undefined,
        language,
        force,
      });

      eventSource.addEventListener("meeting_start", (e) => {
        const data = JSON.parse((e as MessageEvent).data);
        setSummaryProgress({
          currentMeeting: data.current || 0,
          totalMeetings: data.total || meetingIds.length,
          currentMeetingId: data.meeting_id,
          stage: "processing_meeting",
        });
        toast.info(`Processing meeting ${data.meeting_id}...`);
      });

      eventSource.addEventListener("meeting_progress", (e) => {
        const data = JSON.parse((e as MessageEvent).data);
        setSummaryProgress({
          currentMeeting: data.current_meeting || 0,
          totalMeetings: data.total_meetings || meetingIds.length,
          currentMeetingId: data.meeting_id,
          stage: data.stage || "processing",
          documentsProcessed: data.documents_processed,
          totalDocuments: data.total_documents,
        });
      });

      eventSource.addEventListener("meeting_complete", (e) => {
        const data = JSON.parse((e as MessageEvent).data);
        toast.success(`Completed ${data.meeting_id}`);
      });

      eventSource.addEventListener("integrated_report", (e) => {
        const data = JSON.parse((e as MessageEvent).data);
        setSummaryProgress((prev) => ({
          ...prev!,
          stage: "generating_integrated_report",
          currentMeetingId: null,
        }));
        toast.info("Generating integrated report...");
      });

      eventSource.addEventListener("complete", (e) => {
        const data = JSON.parse((e as MessageEvent).data);
        setCurrentSummary(data.summary);
        setSummaryProgress(null);
        setIsSummarizing(false);
        toast.success("Multi-meeting summary completed!");
        eventSource.close();
      });

      eventSource.addEventListener("error", (e) => {
        const data = JSON.parse((e as MessageEvent).data);
        toast.error(data.error || "Error during summarization");
        setSummaryProgress(null);
        setIsSummarizing(false);
        eventSource.close();
      });

      eventSource.onerror = () => {
        toast.error("Connection lost");
        setSummaryProgress(null);
        setIsSummarizing(false);
        eventSource.close();
      };
    } catch (err) {
      console.error("Summarization failed:", err);
      toast.error(err instanceof Error ? err.message : "Failed to summarize");
      setIsSummarizing(false);
      setSummaryProgress(null);
    }
  }

  if (isLoading) {
    return (
      <AuthGuard>
        <div className="flex items-center justify-center h-screen">
          <div className="text-gray-500">Loading meetings...</div>
        </div>
      </AuthGuard>
    );
  }

  if (error || !meetingInfo) {
    return (
      <AuthGuard>
        <div className="max-w-4xl mx-auto p-6">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error || "Failed to load meetings"}
          </div>
          <button
            onClick={() => router.back()}
            className="mt-4 px-4 py-2 text-blue-600 hover:text-blue-800"
          >
            ← Back to Meetings
          </button>
        </div>
      </AuthGuard>
    );
  }

  const allDocuments = currentSummary?.individual_meeting_summaries.flatMap((ms) => ms.summaries) || [];
  const displayedDocuments = showAllDocuments ? allDocuments : allDocuments.slice(0, 10);

  return (
    <AuthGuard>
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div>
          <button
            onClick={() => router.back()}
            className="mb-2 px-3 py-1 text-sm text-blue-600 hover:text-blue-800"
          >
            ← Back to Meetings
          </button>
          <h1 className="text-2xl font-bold text-gray-900">Multi-Meeting Analysis</h1>
          <div className="mt-2 space-y-1">
            {meetingInfo.meeting_infos.map((info) => (
              <div key={info.meeting_id} className="text-sm text-gray-600">
                <span className="font-medium">{info.meeting_id}</span>
                {" - "}
                {info.indexed_documents} indexed / {info.total_documents} total documents
              </div>
            ))}
          </div>
        </div>

        {/* Status Alert */}
        {!meetingInfo.ready_for_analysis && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-yellow-800">
              Some meetings have unindexed documents. Summarization may be incomplete.
            </p>
          </div>
        )}

        {/* Settings Panel */}
        <div className="bg-white shadow-sm rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Analysis Settings</h2>

          <div className="space-y-4">
            {/* Custom Analysis Prompt */}
            <SavedPromptSelector
              value={analysisPrompt}
              onChange={setAnalysisPrompt}
              label="Custom Analysis Prompt"
              description="Focus the analysis on specific aspects (e.g., 'Focus on security implications')"
            />

            {/* Language */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Output Language
              </label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value as AnalysisLanguage)}
                className="w-full border border-gray-300 rounded-md px-3 py-2"
              >
                {Object.entries(languageLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            {/* Force Re-analyze */}
            <div className="flex items-center">
              <input
                type="checkbox"
                id="force"
                checked={force}
                onChange={(e) => setForce(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="force" className="ml-2 text-sm text-gray-700">
                Force re-analyze (ignore cache)
              </label>
            </div>
          </div>

          {/* Summarize Button */}
          <button
            onClick={handleSummarize}
            disabled={isSummarizing || !meetingInfo.ready_for_analysis}
            className={`w-full py-3 rounded-md font-medium ${
              isSummarizing || !meetingInfo.ready_for_analysis
                ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            {isSummarizing ? "Summarizing..." : "Summarize Meetings"}
          </button>
        </div>

        {/* Progress */}
        {summaryProgress && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="font-medium text-blue-900">
                  {summaryProgress.stage === "generating_integrated_report"
                    ? "Generating integrated report..."
                    : `Processing meeting ${summaryProgress.currentMeetingId}...`}
                </span>
                <span className="text-blue-700">
                  Meeting {summaryProgress.currentMeeting} / {summaryProgress.totalMeetings}
                </span>
              </div>
              {summaryProgress.documentsProcessed !== undefined && (
                <div className="text-xs text-blue-700">
                  Documents: {summaryProgress.documentsProcessed} / {summaryProgress.totalDocuments}
                </div>
              )}
              <div className="w-full bg-blue-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all"
                  style={{
                    width: `${
                      (summaryProgress.currentMeeting / summaryProgress.totalMeetings) * 100
                    }%`,
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Integrated Report */}
        {currentSummary && (
          <div className="space-y-6">
            {/* Key Topics */}
            {currentSummary.all_key_topics.length > 0 && (
              <div className="bg-white shadow-sm rounded-lg p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-3">Key Topics Across Meetings</h2>
                <div className="flex flex-wrap gap-2">
                  {currentSummary.all_key_topics.map((topic, i) => (
                    <span
                      key={i}
                      className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                    >
                      {topic}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Integrated Report */}
            <div className="bg-white shadow-sm rounded-lg p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Integrated Analysis Report</h2>
              <MarkdownRenderer content={currentSummary.integrated_report} />
            </div>

            {/* Individual Meeting Summaries */}
            <div className="bg-white shadow-sm rounded-lg p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Individual Meeting Reports</h2>
              <div className="space-y-6">
                {currentSummary.individual_meeting_summaries.map((meetingSummary) => (
                  <div key={meetingSummary.meeting_id} className="border-t pt-4 first:border-t-0 first:pt-0">
                    <h3 className="text-md font-semibold text-gray-800 mb-2">
                      {meetingSummary.meeting_id}
                    </h3>
                    {meetingSummary.key_topics.length > 0 && (
                      <div className="mb-3">
                        <div className="text-sm font-medium text-gray-700 mb-1">Key Topics:</div>
                        <div className="flex flex-wrap gap-1">
                          {meetingSummary.key_topics.map((topic, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs"
                            >
                              {topic}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="prose prose-sm max-w-none">
                      <MarkdownRenderer content={meetingSummary.overall_report} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Document Summaries */}
            <div className="bg-white shadow-sm rounded-lg p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold text-gray-900">
                  Document Summaries ({allDocuments.length})
                </h2>
                {allDocuments.length > 10 && (
                  <button
                    onClick={() => setShowAllDocuments(!showAllDocuments)}
                    className="text-sm text-blue-600 hover:text-blue-800"
                  >
                    {showAllDocuments ? "Show less" : "Show all"}
                  </button>
                )}
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {displayedDocuments.map((doc) => (
                  <DocumentSummaryCard
                    key={doc.document_id}
                    summary={doc}
                    showCachedBadge={true}
                    customPrompt={currentSummary.custom_prompt}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </AuthGuard>
  );
}
