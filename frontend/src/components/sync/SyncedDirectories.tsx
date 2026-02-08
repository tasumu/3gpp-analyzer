"use client";

import { useCallback, useEffect, useState } from "react";
import { getFTPSyncHistory } from "@/lib/api";
import type { SyncHistoryEntry } from "@/lib/types";
import { formatDate } from "@/lib/types";

interface SyncedDirectoriesProps {
  onResync: (directoryPath: string) => void;
  isSyncing: boolean;
  refreshTrigger: number;
}

export function SyncedDirectories({
  onResync,
  isSyncing,
  refreshTrigger,
}: SyncedDirectoriesProps) {
  const [entries, setEntries] = useState<SyncHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadHistory = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getFTPSyncHistory();
      setEntries(data.entries);
    } catch {
      // Silently ignore - section simply won't show
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory, refreshTrigger]);

  if (isLoading && entries.length === 0) {
    return null;
  }

  if (entries.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-medium text-gray-900">
        Synced Directories
      </h3>
      <div className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-100">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className="flex items-center justify-between px-4 py-3"
          >
            <div className="flex-1 min-w-0">
              <div className="font-mono text-sm text-gray-900 truncate">
                {entry.directory_path}
              </div>
              <div className="flex items-center space-x-4 mt-1 text-xs text-gray-500">
                <span>Last synced: {formatDate(entry.last_synced_at)}</span>
                <span>{entry.synced_count} docs</span>
              </div>
            </div>
            <button
              onClick={() => onResync(entry.directory_path)}
              disabled={isSyncing}
              className="ml-4 inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg
                className="h-4 w-4 mr-1"
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
              Re-sync
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
