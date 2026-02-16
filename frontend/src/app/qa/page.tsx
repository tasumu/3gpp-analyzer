"use client";

import { useState, useRef, useEffect } from "react";
import { toast } from "sonner";
import { AuthGuard } from "@/components/AuthGuard";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import { MultipleMeetingSelector } from "@/components/MultipleMeetingSelector";
import {
  askQuestion,
  createQAStream,
  deleteAttachment,
  deleteQAReport,
  generateQAReport,
  listAttachments,
  publishQAReport,
  uploadAttachment,
} from "@/lib/api";
import type {
  AnalysisLanguage,
  Attachment,
  QAEvidence,
  QAMode,
  QAResult,
  QAScope,
} from "@/lib/types";
import { languageLabels, qaModeLabels, qaScopeLabels, qaScopeLabelsJa } from "@/lib/types";

interface ToolStep {
  type: "tool_call" | "tool_result";
  tool: string;
  detail: string;
  args?: Record<string, string>;
}

interface Message {
  id: string;
  type: "user" | "assistant";
  content: string;
  evidences?: QAEvidence[];
  isStreaming?: boolean;
  steps?: ToolStep[];
  resultId?: string;
  reportUrl?: string;
  reportId?: string;
  isPublic?: boolean;
}

const toolDisplayNames: Record<string, string> = {
  list_meeting_documents_enhanced: "Listing documents",
  search_evidence: "Searching",
  get_document_summary: "Reading summary",
  investigate_document: "Investigating document",
  get_document_content: "Reading document",
  list_meeting_attachments: "Checking attachments",
  read_attachment: "Reading attachment",
};

function ToolStepItem({ step }: { step: ToolStep }) {
  const displayName = toolDisplayNames[step.tool] || step.tool;
  const isCall = step.type === "tool_call";

  let callDetail = "";
  if (isCall && step.args) {
    if (step.tool === "investigate_document") {
      const cn = step.args.contribution_number;
      const title = step.args.document_title;
      if (cn && title) {
        callDetail = `${cn}: ${title}`;
      } else if (cn) {
        callDetail = cn;
      }
    } else if (step.tool === "search_evidence") {
      if (step.args.query) callDetail = `"${step.args.query}"`;
    } else if (step.tool === "list_meeting_documents_enhanced") {
      if (step.args.search_text) callDetail = `"${step.args.search_text}"`;
    } else if (step.tool === "get_document_summary") {
      if (step.args.document_id) callDetail = step.args.document_id;
    }
  }

  return (
    <div className="flex items-start gap-2 text-xs text-gray-500">
      <span className="mt-0.5 flex-shrink-0">
        {isCall ? "\u{1F50D}" : "\u{2192}"}
      </span>
      <span>
        {isCall ? (
          <>
            <span className="font-medium text-gray-600">{displayName}</span>
            {callDetail && (
              <span className="text-gray-500 ml-1">- {callDetail}</span>
            )}
          </>
        ) : (
          <span className="text-gray-500">{step.detail}</span>
        )}
      </span>
    </div>
  );
}

function QAEvidenceItem({ evidence, index }: { evidence: QAEvidence; index: number }) {
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
    <div className="border-l-2 border-blue-300 pl-3 py-1 text-sm">
      <div className="text-xs text-gray-500 font-medium">[{index}] {citation}</div>
      <div className="mt-1 text-gray-700">
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

function generateSessionId(): string {
  return crypto.randomUUID();
}

export default function QAPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<QAMode>("agentic");
  const [scope, setScope] = useState<QAScope>("global");
  const [scopeId, setScopeId] = useState<string | null>(null);
  const [scopeIds, setScopeIds] = useState<string[]>([]);
  const [language, setLanguage] = useState<AnalysisLanguage>("ja");
  const [isLoading, setIsLoading] = useState(false);
  const [useStreaming, setUseStreaming] = useState(true);
  const [expandedEvidences, setExpandedEvidences] = useState<Record<string, boolean>>({});
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({});
  const [sessionId, setSessionId] = useState<string>(generateSessionId);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [generatingReportId, setGeneratingReportId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load attachments when meeting changes in agentic mode
  useEffect(() => {
    if (mode === "agentic" && scopeIds.length === 1) {
      listAttachments(scopeIds[0])
        .then(setAttachments)
        .catch(() => setAttachments([]));
    } else {
      setAttachments([]);
    }
  }, [mode, scopeIds]);

  const toggleEvidences = (messageId: string) => {
    setExpandedEvidences((prev) => ({
      ...prev,
      [messageId]: !prev[messageId],
    }));
  };

  const toggleSteps = (messageId: string) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [messageId]: !prev[messageId],
    }));
  };

  const handleModeChange = (newMode: QAMode) => {
    setMode(newMode);
    if (newMode === "agentic") {
      // Agentic mode requires meeting scope
      setScope("meeting");
    }
  };

  const handleScopeChange = (newScope: QAScope) => {
    setScope(newScope);
    if (newScope === "global") {
      setScopeId(null);
      setScopeIds([]);
    }
  };

  const handleMeetingSelect = (meetingIds: string[]) => {
    setScopeIds(meetingIds);
    if (meetingIds.length > 0) {
      setScope("meeting");
    } else {
      setScope("global");
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || scopeIds.length !== 1) return;
    setIsUploading(true);
    try {
      const attachment = await uploadAttachment(scopeIds[0], file);
      setAttachments((prev) => [attachment, ...prev]);
      toast.success(`Uploaded: ${file.name}`);
    } catch {
      toast.error("Upload failed");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDeleteAttachment = async (attachmentId: string) => {
    try {
      await deleteAttachment(attachmentId);
      setAttachments((prev) => prev.filter((a) => a.id !== attachmentId));
      toast.success("Attachment deleted");
    } catch {
      toast.error("Delete failed");
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: question,
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setIsLoading(true);

    const assistantMessageId = (Date.now() + 1).toString();

    try {
      if (useStreaming) {
        // Streaming mode
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMessageId,
            type: "assistant",
            content: "",
            isStreaming: true,
            steps: [],
          },
        ]);

        const eventSource = await createQAStream(
          userMessage.content,
          scope,
          scopeId || undefined,
          scopeIds.length > 0 ? scopeIds : undefined,
          language,
          sessionId,
          mode,
        );

        let fullAnswer = "";
        let evidences: QAEvidence[] = [];
        const steps: ToolStep[] = [];

        // Handle tool_call events (agentic mode)
        eventSource.addEventListener("tool_call", (event) => {
          try {
            const data = JSON.parse(event.data);
            const argsMap = data.args || {};
            const step: ToolStep = {
              type: "tool_call",
              tool: data.tool || "",
              detail: Object.entries(argsMap)
                .map(([k, v]) => `${k}=${v}`)
                .join(", "),
              args: argsMap,
            };
            steps.push(step);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, steps: [...steps] }
                  : m
              )
            );
          } catch {
            console.error("Failed to parse tool_call data");
          }
        });

        // Handle tool_result events (agentic mode)
        eventSource.addEventListener("tool_result", (event) => {
          try {
            const data = JSON.parse(event.data);
            const step: ToolStep = {
              type: "tool_result",
              tool: data.tool || "",
              detail: data.summary || "",
            };
            steps.push(step);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, steps: [...steps] }
                  : m
              )
            );
          } catch {
            console.error("Failed to parse tool_result data");
          }
        });

        // Handle chunk events (streaming text)
        eventSource.addEventListener("chunk", (event) => {
          try {
            const data = JSON.parse(event.data);
            fullAnswer += data.content;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, content: fullAnswer }
                  : m
              )
            );
          } catch {
            console.error("Failed to parse chunk data");
          }
        });

        // Handle evidence events
        eventSource.addEventListener("evidence", (event) => {
          try {
            const data = JSON.parse(event.data);
            evidences.push(data.evidence);
          } catch {
            console.error("Failed to parse evidence data");
          }
        });

        // Handle done event (completion)
        eventSource.addEventListener("done", (event) => {
          try {
            const data = JSON.parse(event.data);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? {
                      ...m,
                      content: fullAnswer || data.answer,
                      evidences,
                      isStreaming: false,
                      resultId: data.result_id,
                    }
                  : m
              )
            );
            eventSource.close();
            setIsLoading(false);
          } catch {
            console.error("Failed to parse done data");
          }
        });

        // Handle error events
        eventSource.addEventListener("error", (event) => {
          try {
            const data = JSON.parse((event as MessageEvent).data);
            toast.error(data.error || "An error occurred");
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, content: "Error: " + (data.error || "Unknown error"), isStreaming: false }
                  : m
              )
            );
          } catch {
            // Connection error, not a JSON error event
          }
          eventSource.close();
          setIsLoading(false);
        });

        eventSource.onerror = () => {
          eventSource.close();
          if (fullAnswer) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, evidences, isStreaming: false }
                  : m
              )
            );
          } else {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, content: "Connection error. Please try again.", isStreaming: false }
                  : m
              )
            );
          }
          setIsLoading(false);
        };
      } else {
        // Non-streaming mode
        const result: QAResult = await askQuestion({
          question: userMessage.content,
          scope,
          scope_id: scopeId,
          scope_ids: scopeIds.length > 0 ? scopeIds : undefined,
          language,
          session_id: sessionId,
          mode,
        });

        setMessages((prev) => [
          ...prev,
          {
            id: assistantMessageId,
            type: "assistant",
            content: result.answer,
            evidences: result.evidences,
            resultId: result.id,
          },
        ]);
      }
    } catch (error) {
      console.error("Q&A failed:", error);
      toast.error("Failed to get answer");
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMessageId,
          type: "assistant",
          content: "Sorry, an error occurred. Please try again.",
        },
      ]);
    } finally {
      if (!useStreaming) {
        setIsLoading(false);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleSaveAsReport = async (messageId: string, resultId: string) => {
    setGeneratingReportId(messageId);
    try {
      const response = await generateQAReport(resultId);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? { ...m, reportUrl: response.download_url, reportId: response.report_id, isPublic: response.is_public }
            : m
        )
      );
      window.open(response.download_url, "_blank");
      toast.success("Report saved");
    } catch (error) {
      console.error("Failed to generate report:", error);
      toast.error("Failed to save report");
    } finally {
      setGeneratingReportId(null);
    }
  };

  const handlePublish = async (messageId: string, reportId: string, isPublic: boolean) => {
    try {
      await publishQAReport(reportId, isPublic);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId ? { ...m, isPublic } : m
        )
      );
      toast.success(isPublic ? "Report published" : "Report unpublished");
    } catch (error) {
      console.error("Failed to update report visibility:", error);
      toast.error("Failed to update report visibility");
    }
  };

  const handleDeleteReport = async (messageId: string, reportId: string) => {
    if (!confirm("Delete this report? This cannot be undone.")) return;
    try {
      await deleteQAReport(reportId);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? { ...m, reportUrl: undefined, reportId: undefined, isPublic: undefined }
            : m
        )
      );
      toast.success("Report deleted");
    } catch (error) {
      console.error("Failed to delete report:", error);
      toast.error("Failed to delete report");
    }
  };

  const clearChat = () => {
    setMessages([]);
    setSessionId(generateSessionId());
  };

  const scopeLabels = language === "ja" ? qaScopeLabelsJa : qaScopeLabels;

  return (
    <AuthGuard>
      <div className="flex flex-col h-[calc(100vh-12rem)]">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Q&A</h1>
            <p className="text-sm text-gray-500 mt-1">
              Ask questions about 3GPP documents. Responses may take a few
              minutes.
            </p>
          </div>
          <button
            onClick={clearChat}
            className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800
                     border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Clear Chat
          </button>
        </div>

        {/* Settings Bar */}
        <div className="flex flex-wrap items-center gap-4 py-4 border-b">
          {/* Mode Selector */}
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Mode:</label>
            <div className="flex rounded-md shadow-sm">
              {(["agentic", "rag"] as QAMode[]).map((m) => (
                <button
                  key={m}
                  onClick={() => handleModeChange(m)}
                  className={`px-3 py-1.5 text-sm font-medium border ${
                    mode === m
                      ? m === "agentic"
                        ? "bg-purple-50 border-purple-500 text-purple-700 z-10"
                        : "bg-blue-50 border-blue-500 text-blue-700 z-10"
                      : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50"
                  } ${
                    m === "agentic" ? "rounded-l-md" : "rounded-r-md -ml-px"
                  }`}
                >
                  {qaModeLabels[m]}
                </button>
              ))}
            </div>
          </div>

          {/* Scope Selector (hidden in agentic mode - always meeting) */}
          {mode === "rag" && (
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700">Scope:</label>
              <div className="flex rounded-md shadow-sm">
                {(["global", "meeting", "document"] as QAScope[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => handleScopeChange(s)}
                    className={`px-3 py-1.5 text-sm font-medium border ${
                      scope === s
                        ? "bg-blue-50 border-blue-500 text-blue-700 z-10"
                        : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50"
                    } ${
                      s === "global"
                        ? "rounded-l-md"
                        : s === "document"
                          ? "rounded-r-md -ml-px"
                          : "-ml-px"
                    }`}
                  >
                    {scopeLabels[s]}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Meeting Selector (shown in agentic mode or meeting scope) */}
          {(mode === "agentic" || scope === "meeting") && (
            <MultipleMeetingSelector
              selectedMeetingIds={scopeIds}
              onSelect={handleMeetingSelect}
              maxSelections={mode === "agentic" ? 1 : 2}
            />
          )}

          {/* Attachments (shown in agentic mode with meeting selected) */}
          {mode === "agentic" && scopeIds.length === 1 && (
            <div className="border-t border-gray-200 pt-2 mt-1">
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-gray-700">
                  Attachments:
                </label>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200
                           text-gray-700 rounded border border-gray-300
                           disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isUploading ? "Uploading..." : "Upload file"}
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileUpload}
                  accept=".docx,.xlsx,.xls,.pdf,.txt,.csv"
                  className="hidden"
                />
                <span className="text-xs text-gray-400">
                  .docx, .xlsx, .txt, .csv
                </span>
              </div>
              {attachments.length > 0 && (
                <div className="mt-1.5 space-y-1">
                  {attachments.map((a) => (
                    <div
                      key={a.id}
                      className="flex items-center gap-2 text-sm text-gray-600"
                    >
                      <span className="text-gray-400">📎</span>
                      <span className="truncate max-w-xs">{a.filename}</span>
                      <span className="text-gray-400 text-xs">
                        ({formatFileSize(a.file_size_bytes)})
                      </span>
                      <button
                        type="button"
                        onClick={() => handleDeleteAttachment(a.id)}
                        className="text-red-400 hover:text-red-600 text-xs ml-auto"
                      >
                        Delete
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Document ID Input (shown when scope is document in RAG mode) */}
          {mode === "rag" && scope === "document" && (
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700">
                Document ID:
              </label>
              <input
                type="text"
                value={scopeId || ""}
                onChange={(e) => setScopeId(e.target.value || null)}
                placeholder="Enter document ID"
                className="w-64 px-3 py-1.5 text-sm border border-gray-300 rounded-md
                         focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}

          {/* Language Selector */}
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

          {/* Streaming Toggle */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="streaming-toggle"
              checked={useStreaming}
              onChange={(e) => setUseStreaming(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="streaming-toggle" className="text-sm text-gray-700">
              Streaming
            </label>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-500 py-12">
              <p className="text-lg">Start a conversation</p>
              <p className="text-sm mt-2">
                {mode === "agentic"
                  ? "Ask questions about a meeting. The agent will plan and investigate."
                  : "Ask any question about 3GPP standardization documents."}
              </p>
            </div>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${
                message.type === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-3 ${
                  message.type === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-900"
                }`}
              >
                {/* Tool Steps (agentic mode) */}
                {message.type === "assistant" && message.steps && message.steps.length > 0 && (
                  <div className="mb-3 pb-2 border-b border-gray-200">
                    <button
                      onClick={() => toggleSteps(message.id)}
                      className="text-xs font-medium text-purple-600 hover:text-purple-800 mb-1"
                    >
                      {expandedSteps[message.id]
                        ? "Hide investigation steps"
                        : `Investigation steps (${message.steps.length})`}
                    </button>
                    {(expandedSteps[message.id] || message.isStreaming) && (
                      <div className="space-y-1 mt-1">
                        {message.steps.map((step, idx) => (
                          <ToolStepItem key={idx} step={step} />
                        ))}
                        {message.isStreaming && !message.content && (
                          <div className="flex items-center gap-2 text-xs text-gray-400">
                            <span className="inline-block w-2 h-2 bg-purple-400 rounded-full animate-pulse" />
                            Investigating...
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {message.isStreaming ? (
                  <>
                    <div className="whitespace-pre-wrap">{message.content}</div>
                    {message.content && (
                      <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-1" />
                    )}
                  </>
                ) : message.content ? (
                  <MarkdownRenderer content={message.content} showCopyButton={true} />
                ) : null}

                {/* Evidences */}
                {message.type === "assistant" && !message.isStreaming && (
                  <div className="mt-4 pt-3 border-t border-gray-300">
                    {message.evidences && message.evidences.length > 0 ? (
                      <>
                        <div className="text-xs font-medium text-gray-600 mb-2">
                          References ({message.evidences.length})
                        </div>
                        <div className="space-y-2">
                          {message.evidences
                            .slice(0, expandedEvidences[message.id] ? undefined : 5)
                            .map((ev, idx) => (
                              <QAEvidenceItem key={idx} evidence={ev} index={idx + 1} />
                            ))}
                          {message.evidences.length > 5 && (
                            <button
                              onClick={() => toggleEvidences(message.id)}
                              className="text-xs text-blue-600 hover:text-blue-800 mt-1"
                            >
                              {expandedEvidences[message.id]
                                ? "Show less"
                                : `+${message.evidences.length - 5} more references`}
                            </button>
                          )}
                        </div>
                      </>
                    ) : (
                      <div className="text-xs text-gray-500 italic">
                        No supporting documents were found for this query.
                      </div>
                    )}
                  </div>
                )}

                {/* Save as Report / Re-download / Publish */}
                {message.type === "assistant" && !message.isStreaming && message.resultId && (
                  <div className="mt-3 pt-2 border-t border-gray-200">
                    {message.reportUrl ? (
                      <div className="flex items-center gap-2 flex-wrap">
                        <a
                          href={message.reportUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-3 py-1.5 text-sm
                                   border border-green-600 text-green-700 font-medium
                                   rounded-md hover:bg-green-50"
                        >
                          Re-download Report
                        </a>
                        {message.reportId && (
                          <>
                            <button
                              onClick={() => handlePublish(message.id, message.reportId!, !message.isPublic)}
                              className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors
                                       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
                              style={{ backgroundColor: message.isPublic ? "#22c55e" : "#d1d5db" }}
                              role="switch"
                              aria-checked={!!message.isPublic}
                              aria-label={message.isPublic ? "Public: click to make private" : "Private: click to share with all users"}
                            >
                              <span
                                className="inline-block h-4 w-4 rounded-full bg-white shadow transition-transform"
                                style={{ transform: message.isPublic ? "translateX(1.375rem)" : "translateX(0.25rem)" }}
                              />
                            </button>
                            <button
                              onClick={() => handleDeleteReport(message.id, message.reportId!)}
                              className="px-3 py-1.5 text-sm border border-red-300 text-red-600
                                       font-medium rounded-md hover:bg-red-50"
                              title="Delete this report"
                            >
                              Delete
                            </button>
                          </>
                        )}
                      </div>
                    ) : (
                      <button
                        onClick={() => handleSaveAsReport(message.id, message.resultId!)}
                        disabled={generatingReportId === message.id}
                        className="px-3 py-1.5 text-sm border border-gray-300 text-gray-700
                                 font-medium rounded-md hover:bg-gray-50
                                 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {generatingReportId === message.id
                          ? "Saving..."
                          : "Save as Report"}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="border-t pt-4">
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question... (Press Enter to send, Shift+Enter for new line)"
              rows={2}
              disabled={isLoading}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg resize-none
                       focus:outline-none focus:ring-2 focus:ring-blue-500
                       disabled:bg-gray-100 disabled:text-gray-500"
            />
            <button
              type="submit"
              disabled={isLoading || !question.trim()}
              className="px-6 py-2 bg-blue-600 text-white font-medium rounded-lg
                       hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {isLoading ? "..." : "Send"}
            </button>
          </div>
        </form>
      </div>
    </AuthGuard>
  );
}
