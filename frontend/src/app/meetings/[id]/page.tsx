"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AuthGuard } from "@/components/AuthGuard";
import { SavedPromptSelector } from "@/components/meeting/SavedPromptSelector";
import {
  getMeetingInfo,
  summarizeMeeting,
  createMeetingSummarizeStream,
  generateMeetingReport,
  listMeetingSummaries,
  createBatchProcessStream,
} from "@/lib/api";
import type {
  AnalysisLanguage,
  DocumentSummary,
  MeetingInfo,
  MeetingReportResponse,
  MeetingSummary,
  BatchProcessEvent,
  BatchProcessProgress,
} from "@/lib/types";
import { languageLabels } from "@/lib/types";

interface SummaryProgress {
  current: number;
  total: number;
  currentDocument: string;
}

function DocumentSummaryCard({ summary }: { summary: DocumentSummary }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-gray-900 truncate">
            {summary.contribution_number}
          </h4>
          <p className="text-sm text-gray-600 truncate">{summary.title}</p>
          {summary.source && (
            <p className="text-xs text-gray-400 mt-1">{summary.source}</p>
          )}
        </div>
        {summary.from_cache && (
          <span className="ml-2 px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
            Cached
          </span>
        )}
      </div>

      <div className="mt-3">
        <p className="text-sm text-gray-700">
          {isExpanded ? summary.summary : summary.summary.substring(0, 200) + "..."}
        </p>
        {summary.summary.length > 200 && (
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
            {summary.key_points.slice(0, isExpanded ? undefined : 3).map((point, idx) => (
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

export default function MeetingDetailPage() {
  const params = useParams();
  const router = useRouter();
  const meetingId = decodeURIComponent(params.id as string);

  const [meetingInfo, setMeetingInfo] = useState<MeetingInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Summarize state
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [summaryProgress, setSummaryProgress] = useState<SummaryProgress | null>(null);
  const [currentSummary, setCurrentSummary] = useState<MeetingSummary | null>(null);
  const [previousSummaries, setPreviousSummaries] = useState<MeetingSummary[]>([]);

  // Report state
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [currentReport, setCurrentReport] = useState<MeetingReportResponse | null>(null);

  // Batch processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [processProgress, setProcessProgress] = useState<BatchProcessProgress | null>(null);

  // Settings
  const [customPrompt, setCustomPrompt] = useState("");
  const [language, setLanguage] = useState<AnalysisLanguage>("ja");
  const [force, setForce] = useState(false);
  const [showAllSummaries, setShowAllSummaries] = useState(false);

  useEffect(() => {
    loadMeetingData();
  }, [meetingId]);

  async function loadMeetingData() {
    try {
      setIsLoading(true);
      setError(null);

      const [info, summaries] = await Promise.all([
        getMeetingInfo(meetingId),
        listMeetingSummaries(meetingId, 10),
      ]);

      setMeetingInfo(info);
      if (summaries.length > 0) {
        setCurrentSummary(summaries[0]);
        setPreviousSummaries(summaries.slice(1));
      }
    } catch (err) {
      console.error("Failed to load meeting data:", err);
      setError(err instanceof Error ? err.message : "Failed to load meeting");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSummarize() {
    if (isSummarizing) return;

    setIsSummarizing(true);
    setSummaryProgress(null);

    try {
      const eventSource = await createMeetingSummarizeStream(
        meetingId,
        customPrompt || undefined,
        language,
        force
      );

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.event === "progress") {
            setSummaryProgress({
              current: data.current,
              total: data.total,
              currentDocument: data.contribution_number || "",
            });
          } else if (data.event === "document_summary") {
            // Individual document summary received
          } else if (data.event === "complete") {
            setCurrentSummary(data.summary);
            setSummaryProgress(null);
            setIsSummarizing(false);
            toast.success("Meeting summary completed");
            eventSource.close();
          } else if (data.event === "error") {
            toast.error(data.message || "Summarization failed");
            setIsSummarizing(false);
            eventSource.close();
          }
        } catch {
          console.error("Failed to parse SSE data");
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setIsSummarizing(false);
        setSummaryProgress(null);
        if (!currentSummary) {
          toast.error("Connection lost. Please try again.");
        }
      };
    } catch (err) {
      console.error("Summarize failed:", err);
      toast.error("Failed to start summarization");
      setIsSummarizing(false);
    }
  }

  async function handleSummarizeNonStreaming() {
    if (isSummarizing) return;

    setIsSummarizing(true);
    try {
      const summary = await summarizeMeeting(meetingId, {
        custom_prompt: customPrompt || null,
        language,
        force,
      });
      setCurrentSummary(summary);
      toast.success("Meeting summary completed");
    } catch (err) {
      console.error("Summarize failed:", err);
      toast.error("Summarization failed");
    } finally {
      setIsSummarizing(false);
    }
  }

  async function handleGenerateReport() {
    if (isGeneratingReport) return;

    setIsGeneratingReport(true);
    try {
      const report = await generateMeetingReport(meetingId, {
        custom_prompt: customPrompt || null,
        language,
      });
      setCurrentReport(report);
      toast.success("Report generated successfully");
    } catch (err) {
      console.error("Report generation failed:", err);
      toast.error("Failed to generate report");
    } finally {
      setIsGeneratingReport(false);
    }
  }

  async function handleBatchProcess() {
    if (isProcessing) return;

    setIsProcessing(true);
    setProcessProgress({
      total: meetingInfo?.unindexed_count || 0,
      processed: 0,
      current_document: null,
      current_status: null,
      current_progress: 0,
      success: 0,
      failed: 0,
    });

    try {
      const eventSource = await createBatchProcessStream(meetingId, {
        force: false,
        concurrency: 3,
      });

      // Helper to handle batch events
      const handleBatchEvent = (event: MessageEvent) => {
        try {
          const data: BatchProcessEvent = JSON.parse(event.data);

          if (data.type === "batch_start") {
            setProcessProgress((prev) =>
              prev ? { ...prev, total: data.total || 0 } : prev
            );
          } else if (data.type === "document_start") {
            setProcessProgress((prev) =>
              prev
                ? {
                    ...prev,
                    current_document:
                      data.contribution_number || data.document_id || null,
                    current_status: "開始中",
                    current_progress: 0,
                  }
                : prev
            );
          } else if (data.type === "document_progress") {
            setProcessProgress((prev) =>
              prev
                ? {
                    ...prev,
                    current_status: data.message || data.status || null,
                    current_progress: data.progress || 0,
                  }
                : prev
            );
          } else if (data.type === "document_complete") {
            setProcessProgress((prev) =>
              prev
                ? {
                    ...prev,
                    processed: prev.processed + 1,
                    success: data.success ? prev.success + 1 : prev.success,
                    failed: data.success ? prev.failed : prev.failed + 1,
                    current_document: null,
                    current_status: null,
                    current_progress: 0,
                  }
                : prev
            );
          } else if (data.type === "batch_complete") {
            setIsProcessing(false);
            setProcessProgress(null);
            loadMeetingData(); // Refresh meeting info
            if (data.failed_count && data.failed_count > 0) {
              toast.warning(
                `処理完了: ${data.success_count}件成功, ${data.failed_count}件失敗`
              );
            } else {
              toast.success(`${data.success_count}件の文書を処理しました`);
            }
            eventSource.close();
          } else if (data.type === "error") {
            toast.error(data.error || "処理中にエラーが発生しました");
            setIsProcessing(false);
            setProcessProgress(null);
            eventSource.close();
          }
        } catch {
          console.error("Failed to parse SSE data");
        }
      };

      // Listen to named events (backend sends event: batch_start, document_start, etc.)
      eventSource.addEventListener("batch_start", handleBatchEvent);
      eventSource.addEventListener("document_start", handleBatchEvent);
      eventSource.addEventListener("document_progress", handleBatchEvent);
      eventSource.addEventListener("document_complete", handleBatchEvent);
      eventSource.addEventListener("batch_complete", handleBatchEvent);
      eventSource.addEventListener("error", handleBatchEvent);

      eventSource.onerror = () => {
        eventSource.close();
        setIsProcessing(false);
        setProcessProgress(null);
        toast.error("接続が切断されました");
      };
    } catch (err) {
      console.error("Batch process failed:", err);
      toast.error("一括処理の開始に失敗しました");
      setIsProcessing(false);
      setProcessProgress(null);
    }
  }

  if (isLoading) {
    return (
      <AuthGuard>
        <div className="text-center py-12 text-gray-500">Loading meeting...</div>
      </AuthGuard>
    );
  }

  if (error || !meetingInfo) {
    return (
      <AuthGuard>
        <div className="space-y-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error || "Meeting not found"}
          </div>
          <button
            onClick={() => router.push("/meetings")}
            className="text-blue-600 hover:text-blue-800"
          >
            Back to meetings
          </button>
        </div>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => router.push("/meetings")}
                className="text-gray-500 hover:text-gray-700"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <h1 className="text-2xl font-bold text-gray-900">{meetingId}</h1>
            </div>
            <p className="text-sm text-gray-500 mt-1">
              {meetingInfo.working_group} - {meetingInfo.meeting_number}
            </p>
          </div>

          <div className="text-right">
            <div className="text-sm text-gray-600">
              {meetingInfo.indexed_documents} / {meetingInfo.total_documents} documents indexed
            </div>
            {meetingInfo.ready_for_analysis ? (
              <span className="text-xs text-green-600 font-medium">Ready for analysis</span>
            ) : (
              <span className="text-xs text-yellow-600 font-medium">Indexing in progress</span>
            )}
          </div>
        </div>

        {/* Indexed-Only Info Banner */}
        {meetingInfo && meetingInfo.total_documents > meetingInfo.indexed_documents && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-start gap-3">
            <svg
              className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <p className="text-sm text-blue-800">
                サマライズおよび分析は<strong>インデックス化済み文書</strong>のみが対象です。
              </p>
              <p className="text-xs text-blue-600 mt-1">
                {meetingInfo.indexed_documents} / {meetingInfo.total_documents} 件の文書が分析対象になります。
                {meetingInfo.unindexed_count > 0 && (
                  <span className="ml-1">
                    （{meetingInfo.unindexed_count}件が未処理）
                  </span>
                )}
              </p>
            </div>
          </div>
        )}

        {/* Batch Processing Progress */}
        {processProgress && (
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-purple-800">
                一括処理中: {processProgress.current_document || "準備中..."}
              </span>
              <span className="text-sm text-purple-600">
                {processProgress.processed} / {processProgress.total}
              </span>
            </div>
            {processProgress.current_status && (
              <p className="text-xs text-purple-600 mb-2">
                {processProgress.current_status}
              </p>
            )}
            <div className="w-full h-2 bg-purple-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-600 rounded-full transition-all"
                style={{
                  width: `${
                    processProgress.total > 0
                      ? (processProgress.processed / processProgress.total) * 100
                      : 0
                  }%`,
                }}
              />
            </div>
            {(processProgress.success > 0 || processProgress.failed > 0) && (
              <p className="text-xs text-purple-600 mt-2">
                成功: {processProgress.success} / 失敗: {processProgress.failed}
              </p>
            )}
          </div>
        )}

        {/* Settings Panel */}
        <div className="bg-white shadow-sm rounded-lg p-6 border border-gray-200">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Analysis Settings</h2>

          <div className="space-y-4">
            {/* Custom Prompt */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Custom Analysis Prompt (optional)
              </label>
              <SavedPromptSelector
                value={customPrompt}
                onChange={setCustomPrompt}
                placeholder="例: セキュリティ関連の議論に焦点を当てて..."
                rows={2}
                disabled={isSummarizing || isGeneratingReport}
              />
            </div>

            <div className="flex flex-wrap items-center gap-4">
              {/* Language */}
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-gray-700">Language:</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value as AnalysisLanguage)}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded-md
                           focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {(Object.keys(languageLabels) as AnalysisLanguage[]).map((lang) => (
                    <option key={lang} value={lang}>
                      {languageLabels[lang]}
                    </option>
                  ))}
                </select>
              </div>

              {/* Force re-analyze */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="force-analyze"
                  checked={force}
                  onChange={(e) => setForce(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="force-analyze" className="text-sm text-gray-700">
                  Force re-analyze (ignore cache)
                </label>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap gap-3 pt-2">
              <button
                onClick={handleSummarize}
                disabled={isSummarizing || isGeneratingReport || isProcessing || !meetingInfo.ready_for_analysis}
                className="px-4 py-2 bg-blue-600 text-white font-medium rounded-md
                         hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {isSummarizing ? "Summarizing..." : "Summarize Meeting"}
              </button>

              <button
                onClick={handleGenerateReport}
                disabled={isSummarizing || isGeneratingReport || isProcessing || !meetingInfo.ready_for_analysis}
                className="px-4 py-2 bg-green-600 text-white font-medium rounded-md
                         hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {isGeneratingReport ? "Generating..." : "Generate Full Report"}
              </button>

              {meetingInfo.unindexed_count > 0 && (
                <button
                  onClick={handleBatchProcess}
                  disabled={isSummarizing || isGeneratingReport || isProcessing}
                  className="px-4 py-2 bg-purple-600 text-white font-medium rounded-md
                           hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  {isProcessing
                    ? "処理中..."
                    : `全文書を一括処理 (${meetingInfo.unindexed_count}件)`}
                </button>
              )}
            </div>

            {!meetingInfo.ready_for_analysis && (
              <p className="text-sm text-yellow-600">
                分析を開始するには、少なくとも1件の文書をインデックス化してください。
              </p>
            )}
          </div>
        </div>

        {/* Progress */}
        {summaryProgress && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-blue-800">
                Processing: {summaryProgress.currentDocument}
              </span>
              <span className="text-sm text-blue-600">
                {summaryProgress.current} / {summaryProgress.total}
              </span>
            </div>
            <div className="w-full h-2 bg-blue-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-600 rounded-full transition-all"
                style={{
                  width: `${(summaryProgress.current / summaryProgress.total) * 100}%`,
                }}
              />
            </div>
          </div>
        )}

        {/* Report Download */}
        {currentReport && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium text-green-800">Report Ready</h3>
                <p className="text-sm text-green-600">
                  Your meeting report has been generated.
                </p>
              </div>
              <a
                href={currentReport.download_url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-green-600 text-white font-medium rounded-md
                         hover:bg-green-700"
              >
                Download Report
              </a>
            </div>
          </div>
        )}

        {/* Current Summary */}
        {currentSummary && (
          <div className="bg-white shadow-sm rounded-lg border border-gray-200">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-medium text-gray-900">Meeting Summary</h2>
                <span className="text-xs text-gray-500">
                  {new Date(currentSummary.created_at).toLocaleString("ja-JP")}
                </span>
              </div>

              {currentSummary.custom_prompt && (
                <div className="mt-2 text-sm text-gray-600">
                  <span className="font-medium">Custom Focus:</span> {currentSummary.custom_prompt}
                </div>
              )}
            </div>

            {/* Key Topics */}
            {currentSummary.key_topics && currentSummary.key_topics.length > 0 && (
              <div className="p-6 border-b border-gray-200">
                <h3 className="text-sm font-medium text-gray-700 mb-2">Key Topics</h3>
                <div className="flex flex-wrap gap-2">
                  {currentSummary.key_topics.map((topic, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-blue-50 text-blue-700 text-sm rounded-full"
                    >
                      {topic}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Overall Report */}
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Overall Summary</h3>
              <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
                {currentSummary.overall_report}
              </div>
            </div>

            {/* Individual Summaries */}
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-700">
                  Document Summaries ({currentSummary.document_count})
                  <span className="ml-2 text-xs text-gray-500 font-normal">
                    (インデックス化済み文書のみ)
                  </span>
                </h3>
                <button
                  onClick={() => setShowAllSummaries(!showAllSummaries)}
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  {showAllSummaries ? "Show less" : "Show all"}
                </button>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {(showAllSummaries
                  ? currentSummary.summaries
                  : currentSummary.summaries.slice(0, 6)
                ).map((summary) => (
                  <DocumentSummaryCard key={summary.document_id} summary={summary} />
                ))}
              </div>

              {!showAllSummaries && currentSummary.summaries.length > 6 && (
                <div className="text-center mt-4 text-sm text-gray-500">
                  +{currentSummary.summaries.length - 6} more documents
                </div>
              )}
            </div>
          </div>
        )}

        {/* Previous Summaries */}
        {previousSummaries.length > 0 && (
          <div className="border-t pt-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Previous Summaries</h2>
            <div className="space-y-2">
              {previousSummaries.map((summary) => (
                <div
                  key={summary.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div>
                    <span className="text-sm text-gray-700">
                      {new Date(summary.created_at).toLocaleString("ja-JP")}
                    </span>
                    {summary.custom_prompt && (
                      <span className="ml-2 text-xs text-gray-500">
                        ({summary.custom_prompt.substring(0, 30)}...)
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">
                    {summary.document_count} documents
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {!currentSummary && !isSummarizing && (
          <div className="text-center py-12 border border-dashed rounded-lg">
            <p className="text-gray-500">No summary yet.</p>
            <p className="text-sm text-gray-400 mt-1">
              Click &quot;Summarize Meeting&quot; to generate a comprehensive summary.
            </p>
          </div>
        )}
      </div>
    </AuthGuard>
  );
}
