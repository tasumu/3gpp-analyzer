"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import {
  runCustomAnalysis,
  listCustomPrompts,
  createCustomPrompt,
  deleteCustomPrompt,
} from "@/lib/api";
import type {
  AnalysisLanguage,
  AnalysisResult,
  CustomPrompt,
} from "@/lib/types";
import { isCustomAnalysis } from "@/lib/types";
import { EvidenceCitation } from "./EvidenceCitation";

interface CustomAnalysisSectionProps {
  documentId: string;
  language: AnalysisLanguage;
}

export function CustomAnalysisSection({
  documentId,
  language,
}: CustomAnalysisSectionProps) {
  const [prompts, setPrompts] = useState<CustomPrompt[]>([]);
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null);
  const [customText, setCustomText] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [isLoadingPrompts, setIsLoadingPrompts] = useState(true);

  useEffect(() => {
    loadPrompts();
  }, []);

  async function loadPrompts() {
    try {
      setIsLoadingPrompts(true);
      const response = await listCustomPrompts();
      setPrompts(response.prompts);
    } catch (error) {
      console.error("Failed to load prompts:", error);
    } finally {
      setIsLoadingPrompts(false);
    }
  }

  async function handleAnalyze() {
    if (!customText.trim()) {
      toast.error("Please enter a prompt");
      return;
    }

    setIsAnalyzing(true);
    try {
      const analysisResult = await runCustomAnalysis(documentId, customText, {
        promptId: selectedPromptId || undefined,
        language,
      });
      setResult(analysisResult);
      toast.success("Custom analysis completed");
    } catch (error) {
      console.error("Custom analysis failed:", error);
      toast.error("Analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function handleSavePrompt() {
    if (!saveName.trim() || !customText.trim()) return;

    try {
      const prompt = await createCustomPrompt(saveName, customText);
      setPrompts([prompt, ...prompts]);
      setShowSaveDialog(false);
      setSaveName("");
      toast.success("Prompt saved");
    } catch (error) {
      console.error("Failed to save prompt:", error);
      toast.error("Failed to save prompt");
    }
  }

  async function handleDeletePrompt(promptId: string) {
    try {
      await deleteCustomPrompt(promptId);
      setPrompts(prompts.filter((p) => p.id !== promptId));
      if (selectedPromptId === promptId) {
        setSelectedPromptId(null);
        setCustomText("");
      }
      toast.success("Prompt deleted");
    } catch (error) {
      console.error("Failed to delete prompt:", error);
      toast.error("Failed to delete prompt");
    }
  }

  function handleSelectPrompt(prompt: CustomPrompt) {
    setSelectedPromptId(prompt.id);
    setCustomText(prompt.prompt_text);
  }

  const customResult =
    result?.result && isCustomAnalysis(result.result) ? result.result : null;

  return (
    <div className="border-t pt-6 mt-6 space-y-4">
      <div>
        <h3 className="text-lg font-medium text-gray-900">Custom Analysis</h3>
        <p className="text-sm text-gray-500">
          Ask a specific question or analyze from a particular perspective.
        </p>
      </div>

      {/* Saved Prompts */}
      {!isLoadingPrompts && prompts.length > 0 && (
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700">
            Saved Prompts
          </label>
          <div className="flex flex-wrap gap-2">
            {prompts.map((prompt) => (
              <div key={prompt.id} className="flex items-center gap-1">
                <button
                  onClick={() => handleSelectPrompt(prompt)}
                  className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                    selectedPromptId === prompt.id
                      ? "bg-blue-100 border-blue-300 text-blue-800"
                      : "bg-gray-50 border-gray-200 hover:bg-gray-100"
                  }`}
                >
                  {prompt.name}
                </button>
                <button
                  onClick={() => handleDeletePrompt(prompt.id)}
                  className="text-gray-400 hover:text-red-500 p-1"
                  title="Delete prompt"
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
        </div>
      )}

      {/* Prompt Input */}
      <div className="space-y-2">
        <textarea
          value={customText}
          onChange={(e) => {
            setCustomText(e.target.value);
            if (selectedPromptId) {
              setSelectedPromptId(null); // Clear selection when user edits
            }
          }}
          placeholder={`Examples:
• Summarize from security perspective
• Does this contain performance requirements?
• What changes are proposed to clause 5.2?
• セキュリティの観点でサマライズして
• XXに関する記述は含まれていますか？`}
          className="w-full h-32 px-3 py-2 text-sm border border-gray-300 rounded-md
                   resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={isAnalyzing}
        />

        <div className="flex gap-2">
          <button
            onClick={handleAnalyze}
            disabled={isAnalyzing || !customText.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-green-600
                     rounded-md hover:bg-green-700 disabled:opacity-50
                     disabled:cursor-not-allowed"
          >
            {isAnalyzing ? "Analyzing..." : "Run Custom Analysis"}
          </button>

          {customText.trim() && !selectedPromptId && (
            <button
              onClick={() => setShowSaveDialog(true)}
              disabled={isAnalyzing}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white
                       border border-gray-300 rounded-md hover:bg-gray-50
                       disabled:opacity-50"
            >
              Save Prompt
            </button>
          )}
        </div>
      </div>

      {/* Save Prompt Dialog */}
      {showSaveDialog && (
        <div className="p-4 bg-gray-50 rounded-lg space-y-3">
          <input
            type="text"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder="Prompt name (e.g., 'Security Analysis')"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md
                     focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <div className="flex gap-2">
            <button
              onClick={handleSavePrompt}
              disabled={!saveName.trim()}
              className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600
                       rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              Save
            </button>
            <button
              onClick={() => {
                setShowSaveDialog(false);
                setSaveName("");
              }}
              className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white
                       border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Result Display */}
      {customResult && (
        <div className="space-y-4 p-4 bg-white border border-gray-200 rounded-lg">
          <div>
            <h4 className="font-medium text-gray-900 mb-2">Result</h4>
            <div className="text-sm text-gray-700 whitespace-pre-wrap">
              {customResult.answer}
            </div>
          </div>

          {customResult.evidences.length > 0 && (
            <div>
              <h4 className="font-medium text-gray-900 mb-2">
                Evidence ({customResult.evidences.length})
              </h4>
              <div className="space-y-2">
                {customResult.evidences.slice(0, 5).map((evidence, i) => (
                  <EvidenceCitation key={i} evidence={evidence} />
                ))}
                {customResult.evidences.length > 5 && (
                  <p className="text-sm text-gray-500">
                    ...and {customResult.evidences.length - 5} more
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
