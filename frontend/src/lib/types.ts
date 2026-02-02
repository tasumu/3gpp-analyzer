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

export interface Document {
  id: string;
  contribution_number: string;
  title: string | null;
  source: string | null;
  meeting_id: string | null;
  meeting_name: string | null;
  status: DocumentStatus;
  error_message: string | null;
  chunk_count: number;
  filename: string;
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

export function isProcessable(status: DocumentStatus): boolean {
  return [
    "metadata_only",
    "downloaded",
    "normalized",
    "chunked",
    "error",
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

// Chunk types

export interface ChunkMetadata {
  document_id: string;
  contribution_number: string;
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

export type AnalysisType = "single" | "compare" | "custom";
export type AnalysisLanguage = "ja" | "en";
export type AnalysisStatus = "pending" | "processing" | "completed" | "failed";
export type ChangeType = "addition" | "modification" | "deletion";
export type Severity = "high" | "medium" | "low";

export interface Change {
  type: ChangeType;
  description: string;
  clause: string | null;
}

export interface Issue {
  description: string;
  severity: Severity;
}

export interface Difference {
  aspect: string;
  doc1_position: string;
  doc2_position: string;
}

export interface Evidence {
  chunk_id: string;
  document_id: string;
  contribution_number: string;
  content: string;
  clause_number: string | null;
  clause_title: string | null;
  page_number: number | null;
  relevance_score: number;
  meeting_id: string | null;
}

export interface SingleAnalysis {
  summary: string;
  changes: Change[];
  issues: Issue[];
  evidences: Evidence[];
}

export interface CompareAnalysis {
  common_points: string[];
  differences: Difference[];
  recommendation: string;
  evidences: Evidence[];
}

export interface AnalysisOptions {
  include_summary?: boolean;
  include_changes?: boolean;
  include_issues?: boolean;
  language?: AnalysisLanguage;
}

export interface AnalysisRequest {
  type: AnalysisType;
  contribution_numbers: string[];
  options?: AnalysisOptions;
  force?: boolean;
}

export interface AnalysisResult {
  id: string;
  document_id: string;
  document_ids: string[];
  contribution_number: string;
  type: AnalysisType;
  status: AnalysisStatus;
  strategy_version: string;
  options: AnalysisOptions;
  result: SingleAnalysis | CompareAnalysis | CustomAnalysisResult | null;
  review_sheet_path: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  created_by: string | null;
}

export interface AnalysisListResponse {
  analyses: AnalysisResult[];
  total: number;
}

export interface AnalysisStartResponse {
  analysis_id: string;
  status: string;
  document_id: string;
  contribution_number: string;
}

// Analysis display helpers
export const changeTypeLabels: Record<ChangeType, string> = {
  addition: "Addition",
  modification: "Modification",
  deletion: "Deletion",
};

export const changeTypeColors: Record<ChangeType, string> = {
  addition: "bg-green-100 text-green-800",
  modification: "bg-yellow-100 text-yellow-800",
  deletion: "bg-red-100 text-red-800",
};

export const severityLabels: Record<Severity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const severityColors: Record<Severity, string> = {
  high: "bg-red-100 text-red-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-blue-100 text-blue-800",
};

export const analysisStatusLabels: Record<AnalysisStatus, string> = {
  pending: "Pending",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
};

export const analysisStatusColors: Record<AnalysisStatus, string> = {
  pending: "bg-gray-100 text-gray-800",
  processing: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

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

export interface CustomAnalysisResult {
  prompt_text: string;
  prompt_id: string | null;
  answer: string;
  evidences: Evidence[];
}

// Type guard for custom analysis
export function isCustomAnalysis(
  result: AnalysisResult["result"]
): result is CustomAnalysisResult {
  return result !== null && "answer" in result && "prompt_text" in result;
}

// Type guard for single analysis
export function isSingleAnalysis(
  result: AnalysisResult["result"]
): result is SingleAnalysis {
  return result !== null && "summary" in result && "changes" in result;
}

// ============================================================================
// Phase 3: Q&A and Meeting Analysis Types
// ============================================================================

// Q&A Types (P3-05)
export type QAScope = "document" | "meeting" | "global";

export interface QARequest {
  question: string;
  scope: QAScope;
  scope_id?: string | null;
  filters?: Record<string, unknown> | null;
  language: AnalysisLanguage;
}

export interface QAEvidence {
  chunk_id: string;
  contribution_number: string;
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
  custom_prompt?: string | null;
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
  custom_prompt?: string | null;
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
