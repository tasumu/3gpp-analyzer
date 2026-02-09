"use client";

import useSWR from "swr";
import { listDocuments, listMeetings } from "../api";
import type { Document, DocumentStatus, DocumentType, Meeting } from "../types";

interface UseDocumentsOptions {
  meeting_id?: string;
  status?: DocumentStatus;
  document_type?: DocumentType;
  path_prefix?: string;
  search_text?: string;
  page?: number;
  page_size?: number;
}

interface UseDocumentsResult {
  documents: Document[];
  total: number;
  page: number;
  pageSize: number;
  isLoading: boolean;
  error: Error | null;
  refresh: () => void;
}

export function useDocuments(options: UseDocumentsOptions = {}): UseDocumentsResult {
  const { meeting_id, status, document_type, path_prefix, search_text, page = 1, page_size = 50 } = options;

  // Create a stable cache key based on parameters
  const cacheKey = ["documents", meeting_id, status, document_type, path_prefix, search_text, page, page_size].filter(Boolean).join("-");

  const { data, error, isLoading, mutate } = useSWR(
    cacheKey,
    () =>
      listDocuments({
        meeting_id,
        status,
        document_type,
        path_prefix,
        search_text,
        page,
        page_size,
      }),
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000, // Dedupe requests within 5 seconds
    }
  );

  return {
    documents: data?.documents ?? [],
    total: data?.total ?? 0,
    page,
    pageSize: page_size,
    isLoading,
    error: error ?? null,
    refresh: () => mutate(),
  };
}

interface UseMeetingsResult {
  meetings: Meeting[];
  isLoading: boolean;
  error: Error | null;
  refresh: () => void;
}

export function useMeetings(): UseMeetingsResult {
  const { data, error, isLoading, mutate } = useSWR(
    "meetings",
    () => listMeetings().then((r) => r.meetings),
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000, // Dedupe requests within 5 seconds
    }
  );

  return {
    meetings: data ?? [],
    isLoading,
    error: error ?? null,
    refresh: () => mutate(),
  };
}
