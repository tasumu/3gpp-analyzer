"use client";

import { useEffect, useState } from "react";
import { createAnalysisStream, getAnalysis } from "@/lib/api";

interface AnalysisProgressProps {
  analysisId: string;
  onComplete: () => void;
  onError: (error: string) => void;
}

interface ProgressState {
  status: string;
  progress: number;
  stage: string;
}

export function AnalysisProgress({
  analysisId,
  onComplete,
  onError,
}: AnalysisProgressProps) {
  const [state, setState] = useState<ProgressState>({
    status: "connecting",
    progress: 0,
    stage: "Connecting...",
  });

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let mounted = true;

    async function connect() {
      try {
        eventSource = await createAnalysisStream(analysisId);

        eventSource.onopen = () => {
          if (mounted) {
            setState({
              status: "processing",
              progress: 10,
              stage: "Starting analysis...",
            });
          }
        };

        eventSource.addEventListener("progress", (event) => {
          if (!mounted) return;
          const data = JSON.parse(event.data);
          setState({
            status: "processing",
            progress: data.progress || 50,
            stage: getStageLabel(data.status || data.stage),
          });
        });

        eventSource.addEventListener("complete", (event) => {
          if (!mounted) return;
          setState({
            status: "completed",
            progress: 100,
            stage: "Analysis complete",
          });
          eventSource?.close();
          onComplete();
        });

        eventSource.addEventListener("error", (event) => {
          if (!mounted) return;
          try {
            const data = JSON.parse((event as MessageEvent).data);
            eventSource?.close();
            onError(data.error || "Analysis failed");
          } catch {
            // Connection error - try polling instead
            pollForCompletion();
          }
        });

        eventSource.onerror = () => {
          // SSE connection error - fall back to polling
          eventSource?.close();
          pollForCompletion();
        };
      } catch (error) {
        console.error("Failed to connect to SSE:", error);
        pollForCompletion();
      }
    }

    async function pollForCompletion() {
      if (!mounted) return;

      const maxAttempts = 60;
      let attempts = 0;

      const poll = async () => {
        if (!mounted || attempts >= maxAttempts) {
          if (mounted) {
            onError("Analysis timed out");
          }
          return;
        }

        try {
          const result = await getAnalysis(analysisId);

          if (!mounted) return;

          if (result.status === "completed") {
            setState({
              status: "completed",
              progress: 100,
              stage: "Analysis complete",
            });
            onComplete();
            return;
          }

          if (result.status === "failed") {
            onError(result.error_message || "Analysis failed");
            return;
          }

          // Still processing
          attempts++;
          setState({
            status: "processing",
            progress: Math.min(10 + attempts * 1.5, 95),
            stage: "Analyzing document...",
          });

          setTimeout(poll, 3000);
        } catch (error) {
          console.error("Polling error:", error);
          attempts++;
          setTimeout(poll, 3000);
        }
      };

      poll();
    }

    connect();

    return () => {
      mounted = false;
      eventSource?.close();
    };
  }, [analysisId, onComplete, onError]);

  function getStageLabel(stage: string): string {
    const labels: Record<string, string> = {
      initializing: "Initializing...",
      fetching_evidence: "Fetching document content...",
      analyzing: "Analyzing with AI...",
      finalizing: "Finalizing results...",
      processing: "Processing...",
    };
    return labels[stage] || stage || "Processing...";
  }

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
      <div className="flex items-center gap-3">
        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600" />
        <div className="flex-1">
          <div className="text-sm font-medium text-blue-800">{state.stage}</div>
          <div className="mt-2 bg-blue-100 rounded-full h-2 overflow-hidden">
            <div
              className="bg-blue-600 h-full transition-all duration-500 ease-out"
              style={{ width: `${state.progress}%` }}
            />
          </div>
          <div className="mt-1 text-xs text-blue-600">{Math.round(state.progress)}%</div>
        </div>
      </div>
    </div>
  );
}
