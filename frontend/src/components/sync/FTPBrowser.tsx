"use client";

import { useCallback, useEffect, useState } from "react";
import { browseFTP, createFTPSyncStream, startFTPSync } from "@/lib/api";
import type { FTPBrowseResponse, FTPSyncProgress } from "@/lib/types";
import { Breadcrumb } from "./Breadcrumb";
import { DirectoryEntry } from "./DirectoryEntry";
import { SyncedDirectories } from "./SyncedDirectories";
import { SyncProgress } from "./SyncProgress";

export function FTPBrowser() {
  const [currentPath, setCurrentPath] = useState("/");
  const [browseData, setBrowseData] = useState<FTPBrowseResponse | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncProgress, setSyncProgress] = useState<FTPSyncProgress | null>(
    null
  );
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const loadDirectory = useCallback(async (path: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await browseFTP(path);
      setBrowseData(data);
      setCurrentPath(path);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load directory");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDirectory("/");
  }, [loadDirectory]);

  const handleNavigate = (path: string) => {
    setSelectedPath(null);
    loadDirectory(path);
  };

  const handleSelect = (entryName: string) => {
    const fullPath = `${currentPath.replace(/\/$/, "")}/${entryName}`;
    setSelectedPath(selectedPath === fullPath ? null : fullPath);
  };

  const handleGoUp = () => {
    if (browseData?.parent) {
      handleNavigate(browseData.parent);
    }
  };

  const handleSyncPath = async (path: string) => {
    try {
      const { sync_id } = await startFTPSync(path);

      // Start SSE stream (now async due to token retrieval)
      const eventSource = await createFTPSyncStream(sync_id);

      const handleSyncEvent = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as FTPSyncProgress;
          setSyncProgress(data);
        } catch (e) {
          console.error("Failed to parse FTP sync progress:", e, event.data);
        }
      };

      const handleTerminalEvent = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as FTPSyncProgress;
          setSyncProgress(data);
        } catch (e) {
          console.error("Failed to parse FTP sync terminal event:", e, event.data);
        } finally {
          eventSource.close();
          loadDirectory(currentPath);
          setRefreshTrigger((prev) => prev + 1);
        }
      };

      eventSource.addEventListener("progress", handleSyncEvent);
      eventSource.addEventListener("complete", handleTerminalEvent);
      eventSource.addEventListener("error", handleTerminalEvent);

      eventSource.onerror = () => {
        eventSource.close();
        setSyncProgress((prev) =>
          prev
            ? { ...prev, status: "error", message: "Connection lost" }
            : null
        );
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start sync");
    }
  };

  const handleSync = async () => {
    if (!selectedPath) return;
    await handleSyncPath(selectedPath);
  };

  const handleCloseProgress = () => {
    setSyncProgress(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Breadcrumb path={currentPath} onNavigate={handleNavigate} />
        <button
          onClick={handleGoUp}
          disabled={currentPath === "/" || isLoading}
          className="inline-flex items-center px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg
            className="h-4 w-4 mr-1"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
          Up
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <svg
              className="h-5 w-5 text-red-400"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <div className="ml-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Sync progress */}
      {syncProgress && (
        <SyncProgress progress={syncProgress} onClose={handleCloseProgress} />
      )}

      {/* Directory listing */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {isLoading ? (
          <div className="animate-pulse p-4 space-y-3">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-10 bg-gray-100 rounded" />
            ))}
          </div>
        ) : browseData?.entries.length === 0 ? (
          <div className="text-center py-12">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
              />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">
              Empty directory
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              This directory has no files or subdirectories.
            </p>
          </div>
        ) : (
          browseData?.entries.map((entry) => (
            <DirectoryEntry
              key={entry.name}
              entry={entry}
              isSelected={
                selectedPath ===
                `${currentPath.replace(/\/$/, "")}/${entry.name}`
              }
              onSelect={() => handleSelect(entry.name)}
              onNavigate={() =>
                handleNavigate(
                  `${currentPath.replace(/\/$/, "")}/${entry.name}`
                )
              }
            />
          ))
        )}
      </div>

      {/* Selected path and sync button */}
      {selectedPath && !syncProgress && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-500">Selected directory:</div>
              <div className="font-mono text-sm text-gray-900">
                {selectedPath}
              </div>
            </div>
            <button
              onClick={handleSync}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              <svg
                className="h-4 w-4 mr-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              Sync This Directory
            </button>
          </div>
        </div>
      )}

      {/* Synced directories for re-sync */}
      <SyncedDirectories
        onResync={handleSyncPath}
        isSyncing={syncProgress?.status === "running"}
        refreshTrigger={refreshTrigger}
      />
    </div>
  );
}
