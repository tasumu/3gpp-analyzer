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
