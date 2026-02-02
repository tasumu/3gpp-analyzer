/**
 * API client for the 3GPP Analyzer backend.
 */

import type {
  AnalysisLanguage,
  AnalysisListResponse,
  AnalysisOptions,
  AnalysisRequest,
  AnalysisResult,
  AnalysisStartResponse,
  ChunkListResponse,
  CustomPrompt,
  CustomPromptsResponse,
  Document,
  ReportPrompt,
  ReportPromptsResponse,
  DocumentListResponse,
  DocumentStatus,
  DocumentSummary,
  DownloadResponse,
  FTPBrowseResponse,
  MeetingInfo,
  MeetingReportRequest,
  MeetingReportResponse,
  MeetingsResponse,
  MeetingSummarizeRequest,
  MeetingSummary,
  ProcessRequest,
  QARequest,
  QAResult,
  QAScope,
} from "./types";
import { getFirebaseAuth } from "./firebase";

// In production, use the direct API URL. In development, use proxy via /api
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

/**
 * Get the current user's Firebase ID token.
 * Returns null if not authenticated.
 * Waits for auth state to be restored if needed.
 */
async function getAuthToken(): Promise<string | null> {
  const auth = getFirebaseAuth();

  // If currentUser is already available, use it
  if (auth.currentUser) {
    return auth.currentUser.getIdToken();
  }

  // Wait for auth state to be restored (happens on page load)
  return new Promise((resolve) => {
    const unsubscribe = auth.onAuthStateChanged((user) => {
      unsubscribe();
      if (user) {
        user.getIdToken().then(resolve).catch(() => resolve(null));
      } else {
        resolve(null);
      }
    });
  });
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
  const url = `${API_BASE}/documents/${documentId}/status/stream?force=${force}&token=${encodeURIComponent(token)}`;
  return new EventSource(url);
}

export async function createStatusWatcher(documentId: string): Promise<EventSource> {
  // SSE needs direct connection to backend with token in query param
  const token = await getAuthToken();
  if (!token) {
    throw new Error("Authentication required for SSE connection");
  }
  const url = `${API_BASE}/documents/${documentId}/status/watch?token=${encodeURIComponent(token)}`;
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
  const url = `${API_BASE}/ftp/sync/${syncId}/stream?token=${encodeURIComponent(token)}`;
  return new EventSource(url);
}

// Chunk APIs

export async function getDocumentChunks(
  documentId: string,
  limit = 500,
): Promise<ChunkListResponse> {
  return fetchApi<ChunkListResponse>(`/documents/${documentId}/chunks?limit=${limit}`);
}

// Analysis APIs (Phase 2)

export async function startAnalysis(
  request: AnalysisRequest,
): Promise<AnalysisStartResponse> {
  return fetchApi<AnalysisStartResponse>("/analysis", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getAnalysis(analysisId: string): Promise<AnalysisResult> {
  return fetchApi<AnalysisResult>(`/analysis/${analysisId}`);
}

export async function listAnalyses(limit = 20): Promise<AnalysisListResponse> {
  return fetchApi<AnalysisListResponse>(`/analysis?limit=${limit}`);
}

export interface AnalyzeDocumentOptions {
  language?: AnalysisLanguage;
  customPrompt?: string;
  force?: boolean;
}

export async function analyzeDocument(
  documentId: string,
  options: AnalyzeDocumentOptions = {},
): Promise<DocumentSummary> {
  return fetchApi<DocumentSummary>(
    `/documents/${documentId}/analyze`,
    {
      method: "POST",
      body: JSON.stringify({
        language: options.language || "ja",
        custom_prompt: options.customPrompt || null,
        force: options.force || false,
      }),
    },
  );
}

export async function getDocumentSummary(
  documentId: string,
  language: AnalysisLanguage = "ja",
  customPrompt?: string,
): Promise<DocumentSummary | null> {
  const params = new URLSearchParams({ language });
  if (customPrompt) {
    params.append("custom_prompt", customPrompt);
  }
  return fetchApi<DocumentSummary | null>(`/documents/${documentId}/summary?${params}`);
}

export async function getDocumentAnalyses(
  documentId: string,
): Promise<AnalysisListResponse> {
  return fetchApi<AnalysisListResponse>(`/documents/${documentId}/analysis`);
}

export async function createAnalysisStream(analysisId: string): Promise<EventSource> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error("Authentication required for SSE connection");
  }
  const url = `${API_BASE}/analysis/${analysisId}/stream?token=${encodeURIComponent(token)}`;
  return new EventSource(url);
}

export function getReviewSheetUrl(analysisId: string): string {
  return `${API_BASE}/downloads/${analysisId}`;
}

// Custom Analysis APIs

export async function runCustomAnalysis(
  documentId: string,
  promptText: string,
  options?: { promptId?: string; language?: AnalysisLanguage },
): Promise<AnalysisResult> {
  return fetchApi<AnalysisResult>(
    `/documents/${documentId}/analyze/custom`,
    {
      method: "POST",
      body: JSON.stringify({
        prompt_text: promptText,
        prompt_id: options?.promptId,
        language: options?.language || "ja",
      }),
    },
  );
}

// Custom Prompts CRUD

export async function listCustomPrompts(): Promise<CustomPromptsResponse> {
  return fetchApi<CustomPromptsResponse>("/prompts");
}

export async function createCustomPrompt(
  name: string,
  promptText: string,
): Promise<CustomPrompt> {
  return fetchApi<CustomPrompt>("/prompts", {
    method: "POST",
    body: JSON.stringify({ name, prompt_text: promptText }),
  });
}

export async function getCustomPrompt(promptId: string): Promise<CustomPrompt> {
  return fetchApi<CustomPrompt>(`/prompts/${promptId}`);
}

export async function updateCustomPrompt(
  promptId: string,
  updates: { name?: string; prompt_text?: string },
): Promise<CustomPrompt> {
  return fetchApi<CustomPrompt>(`/prompts/${promptId}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function deleteCustomPrompt(promptId: string): Promise<void> {
  await fetchApi(`/prompts/${promptId}`, { method: "DELETE" });
}

// Report Prompts CRUD

export async function listReportPrompts(): Promise<ReportPromptsResponse> {
  return fetchApi<ReportPromptsResponse>("/report-prompts");
}

export async function createReportPrompt(
  name: string,
  promptText: string,
): Promise<ReportPrompt> {
  return fetchApi<ReportPrompt>("/report-prompts", {
    method: "POST",
    body: JSON.stringify({ name, prompt_text: promptText }),
  });
}

export async function getReportPrompt(promptId: string): Promise<ReportPrompt> {
  return fetchApi<ReportPrompt>(`/report-prompts/${promptId}`);
}

export async function updateReportPrompt(
  promptId: string,
  updates: { name?: string; prompt_text?: string },
): Promise<ReportPrompt> {
  return fetchApi<ReportPrompt>(`/report-prompts/${promptId}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function deleteReportPrompt(promptId: string): Promise<void> {
  await fetchApi(`/report-prompts/${promptId}`, { method: "DELETE" });
}

// ============================================================================
// Phase 3: Q&A APIs (P3-05)
// ============================================================================

export async function askQuestion(request: QARequest): Promise<QAResult> {
  return fetchApi<QAResult>("/qa", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function createQAStream(
  question: string,
  scope: QAScope = "global",
  scopeId?: string,
  language: AnalysisLanguage = "ja",
): Promise<EventSource> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error("Authentication required for SSE connection");
  }

  const params = new URLSearchParams({
    question,
    scope,
    language,
    token,
  });
  if (scopeId) {
    params.set("scope_id", scopeId);
  }

  const url = `${API_BASE}/qa/stream?${params.toString()}`;
  return new EventSource(url);
}

export async function getQAResult(resultId: string): Promise<QAResult> {
  return fetchApi<QAResult>(`/qa/${resultId}`);
}

export async function listQAResults(
  scope?: QAScope,
  limit = 50,
): Promise<QAResult[]> {
  const params = new URLSearchParams();
  if (scope) params.set("scope", scope);
  params.set("limit", limit.toString());

  return fetchApi<QAResult[]>(`/qa?${params.toString()}`);
}

// ============================================================================
// Phase 3: Meeting Analysis APIs (P3-02, P3-06)
// ============================================================================

export async function getMeetingInfo(meetingId: string): Promise<MeetingInfo> {
  return fetchApi<MeetingInfo>(`/meetings/${encodeURIComponent(meetingId)}/info`);
}

export async function createBatchProcessStream(
  meetingId: string,
  options?: { force?: boolean; concurrency?: number }
): Promise<EventSource> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error("Authentication required for SSE connection");
  }

  const params = new URLSearchParams({
    token,
    force: (options?.force ?? false).toString(),
    concurrency: (options?.concurrency ?? 3).toString(),
  });

  const url = `${API_BASE}/meetings/${encodeURIComponent(meetingId)}/process/stream?${params.toString()}`;
  return new EventSource(url);
}

export async function summarizeMeeting(
  meetingId: string,
  request?: MeetingSummarizeRequest,
): Promise<MeetingSummary> {
  return fetchApi<MeetingSummary>(
    `/meetings/${encodeURIComponent(meetingId)}/summarize`,
    {
      method: "POST",
      body: JSON.stringify(request || { language: "ja" }),
    },
  );
}

export async function createMeetingSummarizeStream(
  meetingId: string,
  options?: {
    analysisPrompt?: string;
    reportPrompt?: string;
    language?: AnalysisLanguage;
    force?: boolean;
  },
): Promise<EventSource> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error("Authentication required for SSE connection");
  }

  const { analysisPrompt, reportPrompt, language = "ja", force = false } = options || {};

  const params = new URLSearchParams({
    language,
    force: force.toString(),
    token,
  });
  if (analysisPrompt) {
    params.set("analysis_prompt", analysisPrompt);
  }
  if (reportPrompt) {
    params.set("report_prompt", reportPrompt);
  }

  const url = `${API_BASE}/meetings/${encodeURIComponent(meetingId)}/summarize/stream?${params.toString()}`;
  return new EventSource(url);
}

export async function getMeetingSummary(
  meetingId: string,
  summaryId: string,
): Promise<MeetingSummary> {
  return fetchApi<MeetingSummary>(
    `/meetings/${encodeURIComponent(meetingId)}/summary/${summaryId}`,
  );
}

export async function listMeetingSummaries(
  meetingId: string,
  limit = 10,
): Promise<MeetingSummary[]> {
  return fetchApi<MeetingSummary[]>(
    `/meetings/${encodeURIComponent(meetingId)}/summaries?limit=${limit}`,
  );
}

export async function generateMeetingReport(
  meetingId: string,
  request?: MeetingReportRequest,
): Promise<MeetingReportResponse> {
  return fetchApi<MeetingReportResponse>(
    `/meetings/${encodeURIComponent(meetingId)}/report`,
    {
      method: "POST",
      body: JSON.stringify(request || { language: "ja" }),
    },
  );
}

export async function getMeetingReport(
  meetingId: string,
  reportId: string,
): Promise<MeetingReportResponse> {
  return fetchApi<MeetingReportResponse>(
    `/meetings/${encodeURIComponent(meetingId)}/report/${reportId}`,
  );
}

export async function listMeetingReports(
  meetingId: string,
  limit = 10,
): Promise<MeetingReportResponse[]> {
  return fetchApi<MeetingReportResponse[]>(
    `/meetings/${encodeURIComponent(meetingId)}/reports?limit=${limit}`,
  );
}

export { ApiError };
