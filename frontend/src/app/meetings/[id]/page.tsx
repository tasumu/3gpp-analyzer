"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AuthGuard } from "@/components/AuthGuard";
import { DocumentSummaryCard } from "@/components/DocumentSummaryCard";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import { SavedPromptSelector } from "@/components/meeting/SavedPromptSelector";
import { SavedReportPromptSelector } from "@/components/meeting/SavedReportPromptSelector";
import {
  getMeetingInfo,
  summarizeMeeting,
  createMeetingSummarizeStream,
  generateMeetingReport,
  listMeetingSummaries,
  createBatchProcessStream,
} from "@/lib/api";
import { useAuth } from "@/lib/auth/AuthContext";
import type {
  AnalysisLanguage,
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

export default function MeetingDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { userInfo } = useAuth();
  const isAdmin = userInfo?.role === "admin";
  const meetingId = decodeURIComponent(params.id as string);

  const [meetingInfo, setMeetingInfo] = useState<MeetingInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Summarize state
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [summaryProgress, setSummaryProgress] = useState<SummaryProgress | null>(null);
  const [currentSummary, setCurrentSummary] = useState<MeetingSummary | null>(null);
  const [latestSummary, setLatestSummary] = useState<MeetingSummary | null>(null);
  const [previousSummaries, setPreviousSummaries] = useState<MeetingSummary[]>([]);

  // Report state
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [currentReport, setCurrentReport] = useState<MeetingReportResponse | null>(null);

  // Batch processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [processProgress, setProcessProgress] = useState<BatchProcessProgress | null>(null);

  // Settings
  const [analysisPrompt, setAnalysisPrompt] = useState("");
  const [reportPrompt, setReportPrompt] = useState("");
  const [language, setLanguage] = useState<AnalysisLanguage>("ja");
  const [force, setForce] = useState(false);
  const [showAllSummaries, setShowAllSummaries] = useState(false);

  const loadMeetingData = useCallback(async () => {
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
        setLatestSummary(summaries[0]);
        setPreviousSummaries(summaries.slice(1));
      }
    } catch (err) {
      console.error("Failed to load meeting data:", err);
      setError(err instanceof Error ? err.message : "Failed to load meeting");
    } finally {
      setIsLoading(false);
    }
  }, [meetingId]);

  useEffect(() => {
    loadMeetingData();
  }, [loadMeetingData]);

  async function handleSummarize() {
    if (isSummarizing) return;

    setIsSummarizing(true);
    setSummaryProgress(null);

    try {
      const eventSource = await createMeetingSummarizeStream(meetingId, {
        analysisPrompt: analysisPrompt || undefined,
        reportPrompt: reportPrompt || undefined,
        language,
        force,
      });

      // Named event handlers (using event.type from SSE event name)
      eventSource.addEventListener("progress", (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          console.log("[SSE] Progress update:", data.current, "/", data.total);
          setSummaryProgress({
            current: data.current,
            total: data.total,
            currentDocument: data.contribution_number || "",
          });
        } catch (e) {
          console.error("Failed to parse SSE progress data:", e, event.data);
        }
      });

      eventSource.addEventListener("document_summary", (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          console.log("[SSE] Document summary:", data.contribution_number);
        } catch (e) {
          console.error("Failed to parse SSE document_summary data:", e, event.data);
        }
      });

      eventSource.addEventListener("overall_report", (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          console.log("[SSE] Overall report received:", data.report?.length, "chars");
        } catch (e) {
          console.error("Failed to parse SSE overall_report data:", e, event.data);
        }
      });

      eventSource.addEventListener("complete", (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          console.log("[SSE] Complete received");
          setCurrentSummary(data.summary);
          setLatestSummary(data.summary);
          toast.success("Meeting summary completed");
        } catch (e) {
          console.error("Failed to parse SSE complete data:", e, event.data);
          toast.error("Failed to process summary completion");
        } finally {
          setSummaryProgress(null);
          setIsSummarizing(false);
          eventSource.close();
        }
      });

      eventSource.addEventListener("error", (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          toast.error(data.error || "Summarization failed");
        } catch {
          toast.error("Summarization failed");
        }
        setIsSummarizing(false);
        setSummaryProgress(null);
        eventSource.close();
      });

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
        analysis_prompt: analysisPrompt || null,
        report_prompt: reportPrompt || null,
        language,
        force,
      });
      setCurrentSummary(summary);
      setLatestSummary(summary);
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
        analysis_prompt: analysisPrompt || null,
        report_prompt: reportPrompt || null,
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
              <span className="text-xs text-yellow-600 font-medium">Processing required</span>
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
                {meetingInfo.indexed_documents} / {meetingInfo.analyzable_documents ?? meetingInfo.total_documents} 件の文書が分析対象になります。
                {meetingInfo.unindexed_count > 0 && (
                  <span className="ml-1">
                    （{meetingInfo.unindexed_count}件が未処理）
                  </span>
                )}
                {(meetingInfo.download_only_documents ?? 0) > 0 && (
                  <span className="ml-1 text-orange-600">
                    （{meetingInfo.download_only_documents}件はDLのみ）
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

        {/* Process All Documents - available to all approved users */}
        {meetingInfo.unindexed_count > 0 && (
          <div className="bg-white shadow-sm rounded-lg p-4 border border-gray-200">
            <button
              onClick={handleBatchProcess}
              disabled={isSummarizing || isGeneratingReport || isProcessing}
              className="px-4 py-2 bg-purple-600 text-white font-medium rounded-md
                       hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {isProcessing
                ? "Processing..."
                : `Process All Documents (${meetingInfo.unindexed_count})`}
            </button>
          </div>
        )}

        {/* Settings Panel - admin only */}
        {isAdmin && (
        <div className="bg-white shadow-sm rounded-lg p-6 border border-gray-200">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Analysis Settings</h2>

          {/* Settings Help Text */}
          <div className="mb-4 p-3 bg-gray-50 rounded-md text-sm text-gray-600 space-y-3">
            {/* Section 1: Button relationship */}
            <div>
              <p className="font-medium text-gray-700 mb-1">機能の関係:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>
                  <strong>Summarize Meeting</strong>: 全寄書を個別にLLM要約し、全体サマリーを生成します。
                </li>
                <li>
                  <strong>Generate Full Report</strong>: 上記の Summarize を内部で実行した後、AIエージェントが追加の深掘り調査を行い、構造化レポート（Markdown）を出力します。
                </li>
              </ul>
              <p className="text-xs text-blue-600 mt-1.5 ml-2">
                先に Summarize Meeting を実行しておくと、Generate Full Report の実行時間を大幅に短縮できます（個別要約がキャッシュから即取得されます）。
              </p>
            </div>

            {/* Section 2: Prompt scope */}
            <div>
              <p className="font-medium text-gray-700 mb-1">プロンプトの影響範囲:</p>
              <div className="ml-2 overflow-x-auto">
                <table className="text-xs border-collapse">
                  <thead>
                    <tr>
                      <th className="text-left pr-4 pb-1 font-medium text-gray-700"></th>
                      <th className="text-left pr-4 pb-1 font-medium text-gray-700">Summarize Meeting</th>
                      <th className="text-left pb-1 font-medium text-gray-700">Generate Full Report</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="pr-4 py-0.5">Analysis Prompt</td>
                      <td className="pr-4 py-0.5">各文書の個別要約</td>
                      <td className="py-0.5">同左（Step 1で使用）</td>
                    </tr>
                    <tr>
                      <td className="pr-4 py-0.5">Report Prompt</td>
                      <td className="pr-4 py-0.5">全体サマリー</td>
                      <td className="py-0.5">全体サマリー + Agent調査の観点</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Section 3: Cache note */}
            <p className="text-xs text-gray-500">
              ※ 異なるプロンプトで分析した結果は別々にキャッシュされます。プロンプトを変更すると全文書の再分析が必要になります。
            </p>
          </div>

          <div className="space-y-4">
            {/* Custom Report Prompt */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Custom Report Prompt (for meeting summary & report)
              </label>
              <SavedReportPromptSelector
                value={reportPrompt}
                onChange={setReportPrompt}
                placeholder="例: 技術的なインパクトに焦点を当てたレポートを生成..."
                rows={2}
                disabled={isSummarizing || isGeneratingReport}
              />
            </div>

            {/* Custom Analysis Prompt */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Custom Analysis Prompt (for document analysis)
              </label>
              <SavedPromptSelector
                value={analysisPrompt}
                onChange={setAnalysisPrompt}
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

            {/* Force re-analyze explanation */}
            <p className="text-xs text-gray-500">
              ※ Force re-analyze: チェックすると個別文書の要約キャッシュを無視して再分析します。Summarize Meeting にのみ影響します（Generate Full Report は内部で Summarize を force=False で呼ぶため影響しません）。
            </p>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-start gap-3 pt-2">
              <div className="flex flex-col items-center">
                <button
                  onClick={handleSummarize}
                  disabled={isSummarizing || isGeneratingReport || isProcessing || !meetingInfo.ready_for_analysis}
                  className="px-4 py-2 bg-blue-600 text-white font-medium rounded-md
                           hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  {isSummarizing ? "Summarizing..." : "Summarize Meeting"}
                </button>
                <span className="text-xs text-gray-500 mt-1">全寄書を個別要約 → 全体サマリー</span>
              </div>

              <span className="text-gray-400 self-center pt-1">→</span>

              <div className="flex flex-col items-center">
                <button
                  onClick={handleGenerateReport}
                  disabled={isSummarizing || isGeneratingReport || isProcessing || !meetingInfo.ready_for_analysis}
                  className="px-4 py-2 bg-green-600 text-white font-medium rounded-md
                           hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  {isGeneratingReport ? "Generating..." : "Generate Full Report"}
                </button>
                <span className="text-xs text-gray-500 mt-1">Summarize + Agent深掘り → レポート</span>
              </div>
            </div>

            {!meetingInfo.ready_for_analysis && (
              <p className="text-sm text-yellow-600">
                分析を開始するには、少なくとも1件の文書をインデックス化してください。
              </p>
            )}
          </div>
        </div>
        )}

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
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-medium text-gray-900">Meeting Summary</h2>
                  {latestSummary && currentSummary.id !== latestSummary.id && (
                    <span className="px-2 py-0.5 text-xs bg-amber-100 text-amber-700 rounded">
                      Viewing past summary
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  {latestSummary && currentSummary.id !== latestSummary.id && (
                    <button
                      onClick={() => setCurrentSummary(latestSummary)}
                      className="text-sm text-blue-600 hover:text-blue-800"
                    >
                      View latest
                    </button>
                  )}
                  <span className="text-xs text-gray-500">
                    {new Date(currentSummary.created_at).toLocaleString("ja-JP")}
                  </span>
                </div>
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
              <MarkdownRenderer content={currentSummary.overall_report} />
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
                  <DocumentSummaryCard
                    key={summary.document_id}
                    summary={summary}
                    customPrompt={currentSummary.custom_prompt}
                  />
                ))}
              </div>

              {!showAllSummaries && currentSummary.summaries.length > 6 && (
                <button
                  onClick={() => setShowAllSummaries(true)}
                  className="w-full mt-4 py-2 text-sm text-blue-600 hover:text-blue-800
                           hover:bg-blue-50 rounded-lg transition-colors"
                >
                  +{currentSummary.summaries.length - 6} more documents
                </button>
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
                <button
                  key={summary.id}
                  onClick={() => setCurrentSummary(summary)}
                  className={`w-full flex items-center justify-between p-3 rounded-lg text-left transition-colors ${
                    currentSummary?.id === summary.id
                      ? "bg-blue-50 border border-blue-200"
                      : "bg-gray-50 hover:bg-gray-100"
                  }`}
                >
                  <div>
                    <span className="text-sm text-gray-700">
                      {new Date(summary.created_at).toLocaleString("ja-JP")}
                    </span>
                    {summary.custom_prompt && (
                      <span className="ml-2 text-xs text-gray-500">
                        ({summary.custom_prompt.substring(0, 30)}
                        {summary.custom_prompt.length > 30 ? "..." : ""})
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">
                    {summary.document_count} documents
                  </span>
                </button>
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
