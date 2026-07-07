# Technical Requirements Document (TRD) v1.0
## Cross-PC File Inventory & Set-Logic Sync Platform ("SetSync")

**Author:** Naidu Suriya
**Date:** July 7, 2026
**Companion to:** PRD v2.0
**Status:** Draft v1.0

---

## 1. Purpose
Defines the technical architecture, data models, APIs, and implementation details required to build SetSync
as specified in PRD v2.0. This document is for engineering implementation reference.

## 2. System Architecture Overview

Four-layer architecture, each independently deployable and testable:

1. **Inventory Agent** (runs on PC-A and PC-B)
2. **Core Service** (set-logic engine + REST API; can run on either PC or a third lightweight host)
3. **Action Executor** (transfer engine abstraction: rclone/Syncthing/custom)
4. **Client Layer** (Web UI + CLI, both consuming the same REST API)

```
[PC-A Agent] --inventory.json/db-->  [Core Service] <--inventory.json/db-- [PC-B Agent]
                                          |
                                   REST API (FastAPI)
                                    /            \
                              [Web UI]         [CLI Tool]
                                          |
                                  [Action Executor]
                                    /            \
                              rclone remote    Syncthing REST
                              (PC-A <-> PC-B)   (optional, Phase 5)
```

## 3. Component Specifications

### 3.1 Inventory Agent
- **Language:** Python 3.11+
- **Responsibilities:** walk configured root directories, compute SHA-256 hash, capture (path, size, mtime, hash), write to local SQLite DB, expose inventory via lightweight HTTP endpoint or push to Core Service.
- **Incremental logic:** before hashing, compare (size, mtime) against last snapshot; skip hash computation if unchanged; hash only new/modified files.
- **Scheduling:** cron/Task Scheduler trigger or on-demand CLI invocation (`setsync-agent scan`).
- **Data store:** SQLite table `files(id, path, size, mtime, hash, scanned_at)`.
- **Failure handling:** partial scan resilience — write incrementally, resumable on crash; log skipped/unreadable files (permission errors) separately.

### 3.2 Core Service (Set-Logic Engine + API)
- **Language/Framework:** Python 3.11+, FastAPI, Uvicorn/Gunicorn.
- **Data ingestion:** pulls latest inventory snapshot from both agents (via HTTP pull or agents push to Core Service endpoint `/inventory/upload`).
- **Set computation:** in-memory dict keyed by hash; O(n) union/intersection/diff computation; cached with invalidation on new inventory upload.
- **Conflict detection:** group by normalized relative path across A and B; if hashes differ → conflict; if hash matches but paths differ → cross-reference match (still counted in intersection).
- **Persistence:** SQLite (or Postgres if scaling later) storing: file records, snapshots, computed set results (cached), audit log, undo log.
- **API framework:** FastAPI with Pydantic models for request/response validation; OpenAPI docs auto-generated at `/docs`.

### 3.3 Action Executor
- **Abstraction interface:** `TransferEngine` with methods `copy(src, dest)`, `move(src, dest)`, `sync(path, mode)`, `dry_run(action)`.
- **Default implementation:** rclone wrapper — shells out to `rclone copy/move/check` against configured remotes (SFTP or local mount pointing to PC-A/PC-B).
- **Optional implementation:** Syncthing REST client — calls Syncthing's `/rest/db/*` and folder override endpoints for near-real-time sync mode (Phase 5).
- **Dry-run:** executes `rclone check` or a stat-only diff to produce a preview payload (what would change) without executing transfer.
- **Undo:** before destructive action, executor snapshots destination file (if overwritten) to a local `.setsync_trash/` directory with retention policy (age/count based cleanup).
- **Progress reporting:** rclone `--progress`/`--stats` JSON output parsed and streamed to Core Service via WebSocket or polling endpoint.

### 3.4 Client Layer

#### Web UI
- **Framework:** React + TypeScript (or lightweight alternative: HTMX + Tailwind for faster MVP).
- **State management:** React Query (or SWR) for API data fetching/caching; WebSocket subscription for live progress/notifications.
- **Key views:** Dashboard (union table + summary strip + filters + search), Conflict Resolution modal, Action Dry-Run modal, Audit Log page, Undo panel.
- **Drag-and-drop:** implemented via HTML5 Drag and Drop API or a library (react-dnd), dropping a row onto PC-A/PC-B column opens the action modal pre-filled.

#### CLI Tool
- **Language:** Python (Click or Typer framework).
- **Commands:** `setsync scan`, `setsync sets --view union|intersection|diff-a|diff-b|conflicts`, `setsync copy <file> --to pcA|pcB`, `setsync move`, `setsync undo`, `setsync log`.
- **Output:** human-readable table by default; `--json` flag for machine-readable output for scripting.

## 4. Data Models

### 4.1 File Record
```
FileRecord {
  id: UUID
  source_pc: enum(A, B)
  path: string (absolute)
  relative_path: string
  size_bytes: int
  mtime: datetime
  hash_sha256: string
  scanned_at: datetime
}
```

### 4.2 Set Computation Result (cached)
```
SetResult {
  computed_at: datetime
  union_count: int
  intersection_count: int
  only_a_count: int
  only_b_count: int
  conflict_count: int
  union: [FileRecord]
  intersection: [hash -> {a_record, b_record}]
  only_a: [FileRecord]
  only_b: [FileRecord]
  conflicts: [{relative_path, a_record, b_record}]
}
```

### 4.3 Action Record (Audit Log)
```
ActionRecord {
  id: UUID
  timestamp: datetime
  action_type: enum(copy, move, sync, undo)
  file_path: string
  source: enum(A, B)
  destination: enum(A, B)
  status: enum(pending, in_progress, completed, failed, undone)
  triggered_by: string (ui, cli, api)
  dry_run_preview: json (nullable)
  error_message: string (nullable)
}
```

### 4.4 Undo Log
```
UndoRecord {
  id: UUID
  action_id: UUID (FK -> ActionRecord)
  backup_path: string
  expires_at: datetime
  restored: boolean
}
```

## 5. REST API Specification (v1)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/inventory/upload` | Agent pushes latest scan snapshot |
| GET | `/inventory/status` | Last scan time, file counts per PC |
| POST | `/sets/compute` | Trigger recomputation of union/intersection/diff |
| GET | `/sets/view?type=union\|intersection\|only_a\|only_b\|conflicts` | Fetch a set view, supports pagination, search, filters |
| GET | `/files/search?q=` | Fuzzy search across all inventoried files |
| POST | `/actions/dry-run` | Preview a copy/move/sync action, returns diff payload |
| POST | `/actions/copy` | Execute copy action `{file_id, destination}` |
| POST | `/actions/move` | Execute move action `{file_id, destination}` |
| POST | `/actions/sync` | Enable/disable continuous sync for a path |
| GET | `/actions/{id}/status` | Poll status of an in-progress action |
| WS | `/actions/stream` | WebSocket stream of live progress events |
| POST | `/actions/{id}/undo` | Revert a completed action within retention window |
| GET | `/audit-log?filters` | Query audit log with filters (date, type, status) |

## 6. Non-Functional / Technical Constraints
- **Performance:** set computation on 100k+ records should complete in under 2 seconds using in-memory hash-keyed dict operations; API responses under 300ms for cached results.
- **Concurrency:** Core Service must handle concurrent scan uploads from both agents without race conditions (use per-PC upload locks).
- **Security:** REST API secured with a local API token (bearer auth); no exposure to public internet by default; LAN-only binding unless explicitly configured otherwise.
- **Reliability:** all write operations (DB, transfer) must be idempotent or safely retryable; partial failures must not corrupt inventory state.
- **Portability:** agents and core service must run on Windows and Linux (cross-platform Python, avoid OS-specific path assumptions — use `pathlib`).
- **Observability:** structured logging (JSON logs) for agent scans, set computations, and action executions; log rotation configured.

## 7. Testing Strategy
- Unit tests for set-logic engine (union/intersection/diff correctness) with synthetic hash-keyed datasets.
- Integration tests for Action Executor against a local rclone test remote (loopback SFTP or local dirs simulating PC-A/PC-B).
- Contract tests for REST API using FastAPI's TestClient + Pydantic schema validation.
- End-to-end test: seed two mock directories with overlapping/unique/conflicting files, verify dashboard counts and action outcomes match expected set results.
- Load test: seed 100k synthetic file records, verify set computation and API latency against NFR5/NFR6 (PRD v2.0).

## 8. Deployment
- **Local-first deployment:** Core Service + Web UI packaged as a single Docker Compose stack (or a Python venv + systemd/Windows service) runnable on either PC or a small always-on device (e.g., mini PC/NAS) on the LAN.
- **Agent deployment:** lightweight standalone script/executable (PyInstaller build) installed on each PC, scheduled via cron/Task Scheduler or run on-demand.
- **Configuration:** `.env`/YAML config for root directories to scan, PC identifiers, API token, undo retention policy, rclone remote definitions.

## 9. Traceability to PRD v2.0
| PRD Requirement | TRD Component |
|---|---|
| FR1-FR4 (Inventory) | Section 3.1 Inventory Agent |
| FR5-FR8 (Set Computation) | Section 3.2 Core Service, Section 4.2 |
| FR9-FR13 (Dashboard) | Section 3.4 Web UI |
| FR14-FR18 (Actions) | Section 3.3 Action Executor, Section 4.3-4.4 |
| FR19-FR20 (Conflicts) | Section 3.2 conflict detection logic |
| FR21-FR23 (API/CLI) | Section 5 REST API, Section 3.4 CLI Tool |
| NFR1-NFR6 | Section 6 Non-Functional/Technical Constraints |
