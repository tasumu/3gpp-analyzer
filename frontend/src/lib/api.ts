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
import { getFirebaseAuth } from "./firebase";

const API_BASE = "/api";
const API_BASE_DIRECT = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

/**
 * Get the current user's Firebase ID token.
 * Returns null if not authenticated.
 */
async function getAuthToken(): Promise<string | null> {
  const auth = getFirebaseAuth();
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken();
}

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
  // Get authentication token
  const token = await getAuthToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options?.headers as Record<string, string>) || {}),
  };

  // Add Authorization header if authenticated
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle authentication errors
  if (response.status === 401) {
    // Redirect to login page
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Authentication required");
  }

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

export async function createStatusStream(
  documentId: string,
  force = false,
): Promise<EventSource> {
  // SSE needs direct connection to backend with token in query param
  const token = await getAuthToken();
  if (!token) {
    throw new Error("Authentication required for SSE connection");
  }
  const url = `${API_BASE_DIRECT}/documents/${documentId}/status/stream?force=${force}&token=${encodeURIComponent(token)}`;
  return new EventSource(url);
}

export async function createStatusWatcher(documentId: string): Promise<EventSource> {
  // SSE needs direct connection to backend with token in query param
  const token = await getAuthToken();
  if (!token) {
    throw new Error("Authentication required for SSE connection");
  }
  const url = `${API_BASE_DIRECT}/documents/${documentId}/status/watch?token=${encodeURIComponent(token)}`;
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

export async function createFTPSyncStream(syncId: string): Promise<EventSource> {
  // SSE needs direct connection to backend with token in query param
  const token = await getAuthToken();
  if (!token) {
    throw new Error("Authentication required for SSE connection");
  }
  const url = `${API_BASE_DIRECT}/ftp/sync/${syncId}/stream?token=${encodeURIComponent(token)}`;
  return new EventSource(url);
}

export { ApiError };
