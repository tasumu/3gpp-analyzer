"use client";

import { useCallback, useEffect, useState } from "react";
import { listDocuments, listMeetings } from "../api";
import type { Document, DocumentStatus, Meeting } from "../types";

interface UseDocumentsOptions {
  meeting_id?: string;
  status?: DocumentStatus;
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
  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const { meeting_id, status, page = 1, page_size = 50 } = options;

  const fetchDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await listDocuments({
        meeting_id,
        status,
        page,
        page_size,
      });
      setDocuments(response.documents);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [meeting_id, status, page, page_size]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  return {
    documents,
    total,
    page,
    pageSize: page_size,
    isLoading,
    error,
    refresh: fetchDocuments,
  };
}

interface UseMeetingsResult {
  meetings: Meeting[];
  isLoading: boolean;
  error: Error | null;
  refresh: () => void;
}

export function useMeetings(): UseMeetingsResult {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchMeetings = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await listMeetings();
      setMeetings(response.meetings);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMeetings();
  }, [fetchMeetings]);

  return {
    meetings,
    isLoading,
    error,
    refresh: fetchMeetings,
  };
}
