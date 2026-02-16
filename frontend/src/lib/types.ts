/**
 * TypeScript types for the 3GPP Analyzer frontend.
 */

export type DocumentStatus =
  | "metadata_only"
  | "downloading"
  | "downloaded"
  | "normalizing"
  | "normalized"
  | "chunking"
  | "chunked"
  | "indexing"
  | "indexed"
  | "error";

export type DocumentType = "contribution" | "other";

export interface Document {
  id: string;
  contribution_number: string | null;
  document_type: DocumentType;
  title: string | null;
  source: string | null;
  meeting_id: string | null;
  meeting_name: string | null;
  status: DocumentStatus;
  analyzable: boolean;
  error_message: string | null;
  chunk_count: number;
  filename: string;
  ftp_path: string;
  file_size_bytes: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
}

export interface Meeting {
  id: string;
  name: string;
  working_group: string;
  document_count: number;
  indexed_count: number;
  analyzable_count: number;
  download_only_count: number;
}

export interface MeetingsResponse {
  meetings: Meeting[];
}

export interface StatusUpdate {
  document_id: string;
  status: DocumentStatus;
  progress: number;
  message: string | null;
  error: string | null;
}

export interface ProcessRequest {
  force?: boolean;
}

export interface DownloadResponse {
  download_url: string;
}

// Status display helpers
export const statusLabels: Record<DocumentStatus, string> = {
  metadata_only: "Metadata Only",
  downloading: "Downloading",
  downloaded: "Downloaded",
  normalizing: "Normalizing",
  normalized: "Normalized",
  chunking: "Chunking",
  chunked: "Chunked",
  indexing: "Indexing",
  indexed: "Indexed",
  error: "Error",
};

export const statusColors: Record<DocumentStatus, string> = {
  metadata_only: "bg-gray-100 text-gray-800",
  downloading: "bg-blue-100 text-blue-800",
  downloaded: "bg-blue-100 text-blue-800",
  normalizing: "bg-yellow-100 text-yellow-800",
  normalized: "bg-yellow-100 text-yellow-800",
  chunking: "bg-yellow-100 text-yellow-800",
  chunked: "bg-yellow-100 text-yellow-800",
  indexing: "bg-purple-100 text-purple-800",
  indexed: "bg-green-100 text-green-800",
  error: "bg-red-100 text-red-800",
};

export function isProcessing(status: DocumentStatus): boolean {
  return [
    "downloading",
    "normalizing",
    "chunking",
    "indexing",
  ].includes(status);
}

export function isProcessable(status: DocumentStatus, analyzable: boolean = true): boolean {
  if (!analyzable) return false;
  return [
    "metadata_only",
    "downloaded",
    "normalized",
    "chunked",
    "error",
    "indexed",
  ].includes(status);
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// FTP Browser types

export interface FTPDirectoryEntry {
  name: string;
  type: "directory" | "file";
  size: number | null;
  synced: boolean;
  synced_count: number | null;
}

export interface FTPBrowseResponse {
  path: string;
  parent: string | null;
  entries: FTPDirectoryEntry[];
}

export interface FTPSyncProgress {
  sync_id: string;
  status: "pending" | "running" | "completed" | "error";
  message: string | null;
  current: number;
  total: number;
  documents_found: number;
  documents_new: number;
  documents_updated: number;
  errors: string[];
}

// Sync history types

export interface SyncHistoryEntry {
  id: string;
  directory_path: string;
  last_synced_at: string;
  documents_found: number;
  documents_new: number;
  documents_updated: number;
  synced_count: number;
}

export interface SyncHistoryResponse {
  entries: SyncHistoryEntry[];
  total: number;
}

// Chunk types

export interface ChunkMetadata {
  document_id: string;
  contribution_number: string | null;
  meeting_id: string | null;
  clause_number: string | null;
  clause_title: string | null;
  page_number: number | null;
  structure_type: string;
  heading_hierarchy: string[];
}

export interface Chunk {
  id: string;
  content: string;
  metadata: ChunkMetadata;
  token_count: number;
  created_at: string;
}

export interface ChunkListResponse {
  chunks: Chunk[];
  total: number;
}

export interface GroupedChunks {
  clause_number: string;
  clause_title: string | null;
  chunks: Chunk[];
}

// Analysis types (Phase 2)

export type AnalysisLanguage = "ja" | "en";

export interface Evidence {
  chunk_id: string;
  document_id: string;
  contribution_number: string | null;
  content: string;
  clause_number: string | null;
  clause_title: string | null;
  page_number: number | null;
  relevance_score: number;
  meeting_id: string | null;
}

// Language display helpers
export const languageLabels: Record<AnalysisLanguage, string> = {
  ja: "日本語",
  en: "English",
};

// Custom analysis types
export interface CustomPrompt {
  id: string;
  user_id: string;
  name: string;
  prompt_text: string;
  created_at: string;
  updated_at: string;
}

export interface CustomPromptsResponse {
  prompts: CustomPrompt[];
}

// Report prompt types
export interface ReportPrompt {
  id: string;
  user_id: string;
  name: string;
  prompt_text: string;
  created_at: string;
  updated_at: string;
}

export interface ReportPromptsResponse {
  prompts: ReportPrompt[];
}

export interface CustomAnalysisResult {
  prompt_text: string;
  prompt_id: string | null;
  answer: string;
  evidences: Evidence[];
}

// ============================================================================
// Phase 3: Q&A and Meeting Analysis Types
// ============================================================================

// Q&A Types (P3-05)
export type QAMode = "rag" | "agentic";
export type QAScope = "document" | "meeting" | "global";

export interface QARequest {
  question: string;
  scope: QAScope;
  scope_id?: string | null;
  scope_ids?: string[];
  filters?: Record<string, unknown> | null;
  language: AnalysisLanguage;
  session_id?: string | null;
  mode?: QAMode;
}

export interface QAEvidence {
  chunk_id: string;
  contribution_number: string | null;
  content: string;
  clause_number: string | null;
  clause_title: string | null;
  page_number: number | null;
  relevance_score: number;
}

export interface QAResult {
  id: string;
  question: string;
  answer: string;
  scope: QAScope;
  scope_id: string | null;
  evidences: QAEvidence[];
  created_at: string;
}

export interface QAReportResponse {
  report_id: string;
  qa_result_id: string;
  download_url: string;
}

// Attachment Types (user-uploaded supplementary files)
export interface Attachment {
  id: string;
  filename: string;
  content_type: string;
  meeting_id: string;
  file_size_bytes: number;
  uploaded_by: string;
  created_at: string;
}

// Meeting Summary Types (P3-02)
export interface DocumentSummary {
  document_id: string;
  contribution_number: string;
  title: string;
  source: string | null;
  summary: string;
  key_points: string[];
  from_cache: boolean;
}

export interface MeetingSummarizeRequest {
  analysis_prompt?: string | null;
  report_prompt?: string | null;
  language: AnalysisLanguage;
  force?: boolean;
}

export interface MeetingSummary {
  id: string;
  meeting_id: string;
  custom_prompt: string | null;
  overall_report: string;
  key_topics: string[];
  document_count: number;
  language: string;
  created_at: string;
  summaries: DocumentSummary[];
}

// Meeting Report Types (P3-06)
export interface MeetingReportRequest {
  analysis_prompt?: string | null;
  report_prompt?: string | null;
  language: AnalysisLanguage;
}

export interface MeetingReportResponse {
  report_id: string;
  meeting_id: string;
  download_url: string;
  summary_id: string;
}

// Meeting Info
export interface MeetingInfo {
  meeting_id: string;
  working_group: string;
  meeting_number: string;
  total_documents: number;
  indexed_documents: number;
  analyzable_documents: number;
  download_only_documents: number;
  unindexed_count: number;
  ready_for_analysis: boolean;
}

// Batch Processing Types
export type BatchProcessEventType =
  | "batch_start"
  | "document_start"
  | "document_progress"
  | "document_complete"
  | "batch_complete"
  | "error";

export interface BatchProcessEvent {
  type: BatchProcessEventType;
  document_id?: string;
  contribution_number?: string;
  index?: number;
  total?: number;
  status?: string;
  progress?: number;
  message?: string;
  success?: boolean;
  error?: string;
  success_count?: number;
  failed_count?: number;
  errors?: Record<string, string>;
}

export interface BatchProcessProgress {
  total: number;
  processed: number;
  current_document: string | null;
  current_status: string | null;
  current_progress: number;
  success: number;
  failed: number;
}

// Multi-Meeting Types (Phase B)
export interface MultiMeetingSummarizeRequest {
  meeting_ids: string[];
  analysis_prompt?: string | null;
  report_prompt?: string | null;
  language: AnalysisLanguage;
  force?: boolean;
}

export interface MultiMeetingSummary {
  id: string;
  meeting_ids: string[];
  custom_prompt: string | null;
  integrated_report: string;
  all_key_topics: string[];
  language: string;
  created_at: string;
  individual_meeting_summaries: MeetingSummary[];
}

export interface MultiMeetingInfo {
  meeting_infos: MeetingInfo[];
  total_documents: number;
  total_indexed_documents: number;
  ready_for_analysis: boolean;
}

// Q&A Scope labels
export const qaScopeLabels: Record<QAScope, string> = {
  document: "Single Document",
  meeting: "Meeting",
  global: "All Documents",
};

export const qaScopeLabelsJa: Record<QAScope, string> = {
  document: "単一寄書",
  meeting: "会合内",
  global: "全体",
};

export const qaModeLabels: Record<QAMode, string> = {
  agentic: "Agentic Search",
  rag: "RAG Search",
};

export const qaModeDescriptions: Record<QAMode, string> = {
  agentic: "Agent が調査計画を立て、複数ツールで能動的に探索",
  rag: "ベクトル検索で関連チャンクを取得し回答",
};

// Batch Operation Types
export interface BatchOperationResponse {
  total: number;
  success_count: number;
  failed_count: number;
  errors: Record<string, string>;
}

// ============================================================================
// User Management Types (Admin Approval Flow)
// ============================================================================

export type UserStatus = "pending" | "approved" | "rejected";
export type UserRole = "user" | "admin";

export interface UserInfo {
  uid: string;
  email: string;
  display_name?: string;
  status: UserStatus;
  role: UserRole;
}

export interface AdminUser {
  uid: string;
  email: string;
  display_name?: string;
  status: UserStatus;
  role: UserRole;
  created_at: string;
  updated_at: string;
  approved_by?: string;
  approved_at?: string;
  last_login_at?: string;
}

export interface UserListResponse {
  users: AdminUser[];
  total: number;
}

// User status display helpers
export const userStatusLabels: Record<UserStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

export const userStatusColors: Record<UserStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

export const userRoleLabels: Record<UserRole, string> = {
  user: "User",
  admin: "Admin",
};
