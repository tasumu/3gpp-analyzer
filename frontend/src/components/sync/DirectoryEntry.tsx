"use client";

import type { FTPDirectoryEntry } from "@/lib/types";
import { formatFileSize } from "@/lib/types";

interface DirectoryEntryProps {
  entry: FTPDirectoryEntry;
  isSelected: boolean;
  onSelect: () => void;
  onNavigate: () => void;
}

export function DirectoryEntry({
  entry,
  isSelected,
  onSelect,
  onNavigate,
}: DirectoryEntryProps) {
  const isDirectory = entry.type === "directory";

  const handleClick = () => {
    if (isDirectory) {
      onNavigate();
    }
  };

  const handleSelect = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isDirectory) {
      onSelect();
    }
  };

  return (
    <div
      className={`flex items-center justify-between px-4 py-3 border-b border-gray-100 hover:bg-gray-50 ${
        isSelected ? "bg-primary-50 hover:bg-primary-100" : ""
      } ${isDirectory ? "cursor-pointer" : ""}`}
      onClick={handleClick}
    >
      <div className="flex items-center space-x-3">
        {isDirectory && (
          <input
            type="radio"
            checked={isSelected}
            onChange={() => {}}
            onClick={handleSelect}
            className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300"
          />
        )}
        {isDirectory ? (
          <svg
            className="h-5 w-5 text-yellow-500"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
          </svg>
        ) : (
          <svg
            className="h-5 w-5 text-gray-400"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
              clipRule="evenodd"
            />
          </svg>
        )}
        <span className="text-sm font-medium text-gray-900">{entry.name}</span>
      </div>

      <div className="flex items-center space-x-4 text-sm text-gray-500">
        {isDirectory && entry.synced ? (
          <span className="flex items-center text-green-600">
            <svg
              className="h-4 w-4 mr-1"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
            {entry.synced_count} docs
          </span>
        ) : isDirectory ? (
          <span className="text-gray-400">Not synced</span>
        ) : (
          <span>{entry.size !== null ? formatFileSize(entry.size) : "-"}</span>
        )}

        {isDirectory && (
          <svg
            className="h-4 w-4 text-gray-400"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
              clipRule="evenodd"
            />
          </svg>
        )}
      </div>
    </div>
  );
}
