export interface UnifiedFileRow {
  id: string;
  name: string;
  relative_path: string;
  size_bytes: number;
  hash_sha256: string;
  location: string; // e.g. "A" | "B" | "Both" | "Conflict" (representing left and right selected sources)
  path_a?: string;
  path_b?: string;
  mtime_a?: string;
  mtime_b?: string;
}

export interface SetSummaryStrip {
  total_files: number;
  union_count: number;
  intersection_count: number;
  only_a_count: number;
  only_b_count: number;
  conflict_count: number;
}

export interface SetViewResponse {
  summary: SetSummaryStrip;
  files: UnifiedFileRow[];
}

export interface ActionResponse {
  id: string;
  timestamp: string;
  action_type: string; // "copy" | "move" | "sync" | "undo"
  file_path: string;
  source: string;
  destination: string;
  status: "pending" | "in_progress" | "completed" | "failed" | "undone";
  triggered_by: "ui" | "cli" | "api";
  dry_run_preview?: any;
  error_message?: string;
}

export interface DryRunResponse {
  action_type: "copy" | "move";
  file_path: string;
  source: string;
  destination: string;
  will_overwrite: boolean;
  source_size: number;
  dest_size?: number;
  source_mtime: string;
  dest_mtime?: string;
  message: string;
}

export interface SourceStatus {
  source_id: string;
  name: string;
  count: number;
  last_scan?: string;
}

export interface InventoryStatus {
  sources: SourceStatus[];
}
