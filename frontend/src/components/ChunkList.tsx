"use client";

import { useState, useMemo } from "react";
import type { Chunk, GroupedChunks } from "@/lib/types";

interface ChunkListProps {
  chunks: Chunk[];
  isLoading?: boolean;
}

function groupChunksByClause(chunks: Chunk[]): GroupedChunks[] {
  const groups = new Map<string, GroupedChunks>();

  for (const chunk of chunks) {
    const clauseNum = chunk.metadata.clause_number || "uncategorized";

    if (!groups.has(clauseNum)) {
      groups.set(clauseNum, {
        clause_number: clauseNum,
        clause_title: chunk.metadata.clause_title,
        chunks: [],
      });
    }

    groups.get(clauseNum)!.chunks.push(chunk);
  }

  return Array.from(groups.values()).sort((a, b) => {
    if (a.clause_number === "uncategorized") return 1;
    if (b.clause_number === "uncategorized") return -1;
    return a.clause_number.localeCompare(b.clause_number, undefined, {
      numeric: true,
    });
  });
}

interface AccordionItemProps {
  group: GroupedChunks;
  isOpen: boolean;
  onToggle: () => void;
}

function AccordionItem({ group, isOpen, onToggle }: AccordionItemProps) {
  return (
    <div className="border border-gray-200 rounded-md mb-2">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 text-left bg-gray-50 hover:bg-gray-100 rounded-t-md"
      >
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-gray-600">
            {group.clause_number === "uncategorized"
              ? "(No clause)"
              : group.clause_number}
          </span>
          {group.clause_title && (
            <span className="text-sm text-gray-800">{group.clause_title}</span>
          )}
          <span className="text-xs text-gray-500">
            ({group.chunks.length} chunk{group.chunks.length !== 1 ? "s" : ""})
          </span>
        </div>
        <svg
          className={`w-5 h-5 text-gray-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {isOpen && (
        <div className="px-4 py-3 space-y-3 bg-white rounded-b-md">
          {group.chunks.map((chunk, index) => (
            <div key={chunk.id} className="border-l-2 border-gray-200 pl-3">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <span>Chunk {index + 1}</span>
                {chunk.metadata.page_number && (
                  <span>| Page {chunk.metadata.page_number}</span>
                )}
                <span>| {chunk.token_count} tokens</span>
                <span className="capitalize">
                  | {chunk.metadata.structure_type}
                </span>
              </div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">
                {chunk.content}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ChunkList({ chunks, isLoading }: ChunkListProps) {
  const [openSections, setOpenSections] = useState<Set<string>>(new Set());

  const groupedChunks = useMemo(() => groupChunksByClause(chunks), [chunks]);

  const toggleSection = (clauseNumber: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(clauseNumber)) {
        next.delete(clauseNumber);
      } else {
        next.add(clauseNumber);
      }
      return next;
    });
  };

  const expandAll = () => {
    setOpenSections(new Set(groupedChunks.map((g) => g.clause_number)));
  };

  const collapseAll = () => {
    setOpenSections(new Set());
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 bg-gray-200 rounded-md" />
        ))}
      </div>
    );
  }

  if (chunks.length === 0) {
    return <p className="text-sm text-gray-500">No chunks available.</p>;
  }

  return (
    <div>
      <div className="flex justify-end gap-2 mb-3">
        <button
          onClick={expandAll}
          className="text-xs text-primary-600 hover:text-primary-800"
        >
          Expand all
        </button>
        <span className="text-gray-300">|</span>
        <button
          onClick={collapseAll}
          className="text-xs text-primary-600 hover:text-primary-800"
        >
          Collapse all
        </button>
      </div>

      <div>
        {groupedChunks.map((group) => (
          <AccordionItem
            key={group.clause_number}
            group={group}
            isOpen={openSections.has(group.clause_number)}
            onToggle={() => toggleSection(group.clause_number)}
          />
        ))}
      </div>
    </div>
  );
}
