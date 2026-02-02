"use client";

import { useState, useRef, useEffect } from "react";
import { toast } from "sonner";
import { AuthGuard } from "@/components/AuthGuard";
import { MeetingSelector } from "@/components/MeetingSelector";
import { askQuestion, createQAStream } from "@/lib/api";
import type { AnalysisLanguage, QAEvidence, QAResult, QAScope } from "@/lib/types";
import { languageLabels, qaScopeLabels, qaScopeLabelsJa } from "@/lib/types";

interface Message {
  id: string;
  type: "user" | "assistant";
  content: string;
  evidences?: QAEvidence[];
  isStreaming?: boolean;
}

function QAEvidenceItem({ evidence }: { evidence: QAEvidence }) {
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
      <div className="text-xs text-gray-500 font-medium">{citation}</div>
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

export default function QAPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [scope, setScope] = useState<QAScope>("global");
  const [scopeId, setScopeId] = useState<string | null>(null);
  const [language, setLanguage] = useState<AnalysisLanguage>("ja");
  const [isLoading, setIsLoading] = useState(false);
  const [useStreaming, setUseStreaming] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleScopeChange = (newScope: QAScope) => {
    setScope(newScope);
    if (newScope === "global") {
      setScopeId(null);
    }
  };

  const handleMeetingSelect = (meetingId: string | null) => {
    setScopeId(meetingId);
    if (meetingId) {
      setScope("meeting");
    } else {
      setScope("global");
    }
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
          },
        ]);

        const eventSource = await createQAStream(
          userMessage.content,
          scope,
          scopeId || undefined,
          language
        );

        let fullAnswer = "";
        let evidences: QAEvidence[] = [];

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
                  ? { ...m, content: fullAnswer || data.answer, evidences, isStreaming: false }
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
          language,
        });

        setMessages((prev) => [
          ...prev,
          {
            id: assistantMessageId,
            type: "assistant",
            content: result.answer,
            evidences: result.evidences,
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

  const clearChat = () => {
    setMessages([]);
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
              Ask questions about 3GPP documents using RAG-powered search.
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
          {/* Scope Selector */}
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

          {/* Meeting Selector (shown when scope is meeting) */}
          {scope === "meeting" && (
            <MeetingSelector
              selectedMeetingId={scopeId}
              onSelect={handleMeetingSelect}
            />
          )}

          {/* Document ID Input (shown when scope is document) */}
          {scope === "document" && (
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
                Ask any question about 3GPP standardization documents.
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
                <div className="whitespace-pre-wrap">{message.content}</div>
                {message.isStreaming && (
                  <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-1" />
                )}

                {/* Evidences */}
                {message.type === "assistant" && !message.isStreaming && (
                  <div className="mt-4 pt-3 border-t border-gray-300">
                    {message.evidences && message.evidences.length > 0 ? (
                      <>
                        <div className="text-xs font-medium text-gray-600 mb-2">
                          References ({message.evidences.length})
                        </div>
                        <div className="space-y-2">
                          {message.evidences.slice(0, 5).map((ev, idx) => (
                            <QAEvidenceItem key={idx} evidence={ev} />
                          ))}
                          {message.evidences.length > 5 && (
                            <div className="text-xs text-gray-500">
                              +{message.evidences.length - 5} more references
                            </div>
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
