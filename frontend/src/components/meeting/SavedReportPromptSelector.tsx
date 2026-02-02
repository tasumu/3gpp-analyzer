"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import {
  listReportPrompts,
  createReportPrompt,
  deleteReportPrompt,
} from "@/lib/api";
import type { ReportPrompt } from "@/lib/types";

interface SavedReportPromptSelectorProps {
  value: string;
  onChange: (text: string) => void;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
}

export function SavedReportPromptSelector({
  value,
  onChange,
  placeholder = "例: セキュリティの観点でレポートを生成...",
  rows = 2,
  disabled = false,
}: SavedReportPromptSelectorProps) {
  const [prompts, setPrompts] = useState<ReportPrompt[]>([]);
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null);
  const [isLoadingPrompts, setIsLoadingPrompts] = useState(true);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    loadPrompts();
  }, []);

  async function loadPrompts() {
    try {
      setIsLoadingPrompts(true);
      const response = await listReportPrompts();
      setPrompts(response.prompts);
    } catch (error) {
      console.error("Failed to load report prompts:", error);
    } finally {
      setIsLoadingPrompts(false);
    }
  }

  function handleSelectPrompt(prompt: ReportPrompt) {
    setSelectedPromptId(prompt.id);
    onChange(prompt.prompt_text);
  }

  function handleTextChange(text: string) {
    onChange(text);
    // Clear selection when user edits the text
    if (selectedPromptId) {
      const selectedPrompt = prompts.find((p) => p.id === selectedPromptId);
      if (selectedPrompt && text !== selectedPrompt.prompt_text) {
        setSelectedPromptId(null);
      }
    }
  }

  async function handleSavePrompt() {
    if (!saveName.trim() || !value.trim()) return;

    setIsSaving(true);
    try {
      const prompt = await createReportPrompt(saveName, value);
      setPrompts([prompt, ...prompts]);
      setSelectedPromptId(prompt.id);
      setShowSaveDialog(false);
      setSaveName("");
      toast.success("レポートプロンプトを保存しました");
    } catch (error) {
      console.error("Failed to save report prompt:", error);
      toast.error("レポートプロンプトの保存に失敗しました");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDeletePrompt(promptId: string, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await deleteReportPrompt(promptId);
      setPrompts(prompts.filter((p) => p.id !== promptId));
      if (selectedPromptId === promptId) {
        setSelectedPromptId(null);
      }
      toast.success("レポートプロンプトを削除しました");
    } catch (error) {
      console.error("Failed to delete report prompt:", error);
      toast.error("レポートプロンプトの削除に失敗しました");
    }
  }

  const canSave = value.trim() && !selectedPromptId;

  return (
    <div className="space-y-2">
      {/* Saved Prompts */}
      {!isLoadingPrompts && prompts.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {prompts.map((prompt) => (
            <div key={prompt.id} className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => handleSelectPrompt(prompt)}
                disabled={disabled}
                className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                  selectedPromptId === prompt.id
                    ? "bg-green-100 border-green-300 text-green-800"
                    : "bg-gray-50 border-gray-200 hover:bg-gray-100"
                } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
              >
                {prompt.name}
              </button>
              <button
                type="button"
                onClick={(e) => handleDeletePrompt(prompt.id, e)}
                disabled={disabled}
                className="text-gray-400 hover:text-red-500 p-1 disabled:opacity-50"
                title="レポートプロンプトを削除"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Text Input */}
      <textarea
        value={value}
        onChange={(e) => handleTextChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        disabled={disabled}
        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm
                 focus:outline-none focus:ring-2 focus:ring-green-500
                 disabled:bg-gray-100 disabled:cursor-not-allowed"
      />

      {/* Save Button */}
      {canSave && !disabled && (
        <div className="flex items-center gap-2">
          {!showSaveDialog ? (
            <button
              type="button"
              onClick={() => setShowSaveDialog(true)}
              className="text-sm text-green-600 hover:text-green-800"
            >
              このレポートプロンプトを保存
            </button>
          ) : (
            <div className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg w-full">
              <input
                type="text"
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                placeholder="プロンプト名（例: セキュリティレポート）"
                className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md
                         focus:outline-none focus:ring-2 focus:ring-green-500"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && saveName.trim()) {
                    handleSavePrompt();
                  }
                }}
              />
              <button
                type="button"
                onClick={handleSavePrompt}
                disabled={!saveName.trim() || isSaving}
                className="px-3 py-1.5 text-sm font-medium text-white bg-green-600
                         rounded-md hover:bg-green-700 disabled:opacity-50"
              >
                {isSaving ? "保存中..." : "保存"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowSaveDialog(false);
                  setSaveName("");
                }}
                className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white
                         border border-gray-300 rounded-md hover:bg-gray-50"
              >
                キャンセル
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
