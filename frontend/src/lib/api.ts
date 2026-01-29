/**
 * API client for the 3GPP Analyzer backend.
 */

import type {
  Document,
  DocumentListResponse,
  DocumentStatus,
  DownloadResponse,
  FTPBrowseResponse,
  MeetingsResponse,
  ProcessRequest,
} from "./types";

const API_BASE = "/api";
const API_BASE_DIRECT = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, error.detail || "Unknown error");
  }

  return response.json();
}

// Document APIs

export async function listDocuments(params?: {
  meeting_id?: string;
  status?: DocumentStatus;
  page?: number;
  page_size?: number;
}): Promise<DocumentListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.meeting_id) searchParams.set("meeting_id", params.meeting_id);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.page) searchParams.set("page", params.page.toString());
  if (params?.page_size) searchParams.set("page_size", params.page_size.toString());

  const query = searchParams.toString();
  return fetchApi<DocumentListResponse>(`/documents${query ? `?${query}` : ""}`);
}

export async function getDocument(documentId: string): Promise<Document> {
  return fetchApi<Document>(`/documents/${documentId}`);
}

export async function processDocument(
  documentId: string,
  request?: ProcessRequest,
): Promise<Document> {
  return fetchApi<Document>(`/documents/${documentId}/process`, {
    method: "POST",
    body: JSON.stringify(request || {}),
  });
}

export async function deleteDocument(documentId: string): Promise<void> {
  await fetchApi(`/documents/${documentId}`, {
    method: "DELETE",
  });
}

export async function getDownloadUrl(
  documentId: string,
  normalized = true,
): Promise<string> {
  const response = await fetchApi<DownloadResponse>(
    `/documents/${documentId}/download?normalized=${normalized}`,
  );
  return response.download_url;
}

// Meeting APIs

export async function listMeetings(): Promise<MeetingsResponse> {
  return fetchApi<MeetingsResponse>("/meetings");
}

// SSE helpers

export function createStatusStream(
  documentId: string,
  force = false,
): EventSource {
  // SSE needs direct connection to backend
  const url = `${API_BASE_DIRECT}/documents/${documentId}/status/stream?force=${force}`;
  return new EventSource(url);
}

export function createStatusWatcher(documentId: string): EventSource {
  // SSE needs direct connection to backend
  const url = `${API_BASE_DIRECT}/documents/${documentId}/status/watch`;
  return new EventSource(url);
}

// FTP Browser APIs

export async function browseFTP(path: string = "/"): Promise<FTPBrowseResponse> {
  return fetchApi<FTPBrowseResponse>(`/ftp/browse?path=${encodeURIComponent(path)}`);
}

export async function startFTPSync(
  path: string,
  pathPattern?: string,
): Promise<{ sync_id: string }> {
  return fetchApi<{ sync_id: string }>("/ftp/sync", {
    method: "POST",
    body: JSON.stringify({ path, path_pattern: pathPattern }),
  });
}

export function createFTPSyncStream(syncId: string): EventSource {
  // SSE needs direct connection to backend (Next.js rewrites don't handle streaming well)
  const url = `${API_BASE_DIRECT}/ftp/sync/${syncId}/stream`;
  return new EventSource(url);
}

export { ApiError };
