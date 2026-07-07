# Product Requirements Document (PRD) v2.0
## Cross-PC File Inventory & Set-Logic Sync Platform ("SetSync")

**Author:** Naidu Suriya
**Date:** July 7, 2026
**Status:** Draft v2.0 (supersedes v1.0)

---

## 1. Problem Statement
Files are scattered across two PCs (PC-A and PC-B) with no unified visibility into what exists where.
There is no reliable way to see the union, intersection, or differences between the two file sets, and no
mechanism to move/copy/sync a specific file to a chosen machine on demand, with confidence that nothing
will be lost or silently overwritten.

## 2. Vision
Not just a sync utility — a trustworthy, fast, API-first "single pane of glass" over both PCs' file systems,
where set logic (union/intersection/difference) is the primary mental model, safety is default (dry-run,
undo, audit log), and every action available in the UI is also available via API/CLI.

## 3. Goals
- Provide a single unified view of all files across PC-A and PC-B, searchable and filterable in real time.
- Compute Union, Intersection, and Differences based on content hash (not filename).
- Allow copy/move/sync of any file to a chosen PC on demand, with a pre-action dry-run preview.
- Make every action reversible via an undo log and fully auditable.
- Expose all functionality via REST API first; UI and CLI are both clients of the same API.
- Keep re-scans fast via incremental hashing (only re-hash changed files).

## 4. Non-Goals
- Not a full cloud storage replacement.
- Not real-time collaborative editing or automatic conflict "smart merge."
- Not supporting more than 2 machines in v1 (architecture allows future N-machine extension).
- Not building a heavy always-on background sync engine as the default mode (on-demand-first).

## 5. Users
- Primary user: Naidu Suriya (single user, dual-PC personal setup).
- Secondary use case: power-user scripting via CLI/API for automation.

## 6. Core Concepts (Set Logic Mapping)
| Set Concept | Definition | UI Representation |
|---|---|---|
| Set A | All files on PC-A | Filtered view "PC-A only" |
| Set B | All files on PC-B | Filtered view "PC-B only" |
| A ∪ B | All unique files across both PCs | Default "All Files" table |
| A ∩ B | Files present on both PCs (same content hash) | Filtered view "On Both" |
| A − B | Files only on PC-A | Filtered view "Only on PC-A" |
| B − A | Files only on PC-B | Filtered view "Only on PC-B" |
| Conflict | Same path, different hash on A and B | Filtered view "Conflicts" |

File identity = SHA-256 content hash, not path/filename, so renamed/moved duplicates still match correctly.

## 7. Differentiating "Awesome" Features (v2 additions)
- **Dry-run preview**: every copy/move/overwrite shows exactly what will change before execution.
- **Undo log**: last N actions reversible with one click (soft-delete/trash-log, not permanent until confirmed).
- **Live summary strip**: total files, # union/intersection/A-only/B-only/conflicts, updated live.
- **Fuzzy search**: instant search by name, extension, size range, date range.
- **Incremental hashing**: skip unchanged files (size+mtime match) to make re-scans fast at scale.
- **Drag-and-drop UI**: drag a file between PC-A/PC-B columns as primary action gesture.
- **Real-time progress**: per-file progress bar + OS notification on batch completion.
- **API-first design**: REST API is the source of truth; UI and CLI both consume it.
- **CLI companion**: scriptable parity with UI actions, JSON output for automation.
- **Audit log**: filterable history of every action (what moved, from/to, when, who/what triggered it).

## 8. Functional Requirements

### 8.1 Inventory
- FR1: Scan configurable root directories on each PC.
- FR2: Compute SHA-256 hash, size, mtime, full path per file.
- FR3: Store timestamped versioned snapshots (not just latest state).
- FR4: Incremental re-scan — skip re-hashing files unchanged in size+mtime.

### 8.2 Set Computation
- FR5: Compute Union, Intersection, A-only, B-only via hash key.
- FR6: Flag "same path, different hash" as Conflict (not silently resolved).
- FR7: Treat "same hash, different path" as a Match, not a conflict.
- FR8: Recompute on demand (manual trigger) or on schedule (configurable interval).

### 8.3 Dashboard / Unified View
- FR9: Table with filename, path, size, short hash, location (A/B/Both), last modified.
- FR10: Filters: All, On Both, Only PC-A, Only PC-B, Conflicts.
- FR11: Fuzzy search by name/extension/size range/date range.
- FR12: Live summary counts strip at top of dashboard.
- FR13: Drag-and-drop between PC-A/PC-B columns triggers action modal.

### 8.4 Actions
- FR14: Copy/Move to PC-A or PC-B for any selected file, single or batch.
- FR15: Dry-run preview modal before any destructive/overwrite action.
- FR16: Optional per-file/folder "keep synced" toggle (opt-in continuous sync).
- FR17: Real-time status (pending/in-progress/completed/failed) with progress bar.
- FR18: Undo last action(s) within a configurable retention window.

### 8.5 Conflict Handling
- FR19: Present both file versions (metadata + hash) side by side when conflict detected.
- FR20: User chooses: keep A, keep B, keep both (auto-rename), or manual merge (external).

### 8.6 API & CLI
- FR21: All actions (scan, compute sets, copy/move/sync, undo) available via REST API.
- FR22: CLI tool wraps the same API, supports JSON output for scripting.
- FR23: Audit log queryable via API (filter by date, action type, file, result).

## 9. Non-Functional Requirements
- NFR1: Scanning/hashing runs as background job; UI never blocks.
- NFR2: Works over LAN, no mandatory internet/cloud dependency.
- NFR3: All actions logged for audit; undo retention configurable (default 7 days or 100 actions).
- NFR4: Transfer engine abstracted behind an interface so rclone/Syncthing/custom can be swapped.
- NFR5: Scales to 100k+ files per PC without significant UI/query slowdown (indexed SQLite).
- NFR6: API response times under 300ms for set-computation queries on cached inventory.

## 10. User Flow (Primary)
1. User opens dashboard → live summary strip + Union table loads.
2. User searches or filters (e.g., "Only on PC-A").
3. User drags a file from PC-A column to PC-B column (or selects + clicks Copy).
4. Dry-run modal shows destination path, action type, and any conflict warning.
5. User confirms → real-time progress bar shows transfer → notification on completion.
6. Action logged in audit log; dashboard recomputes sets automatically.
7. If needed, user opens Undo panel and reverts the last action.

## 11. Milestones
| Phase | Scope |
|---|---|
| Phase 1 (MVP) | Scanning agents, SQLite inventory, CLI-only set computation |
| Phase 2 | REST API for scan/set-computation; basic web table UI with filters/search |
| Phase 3 | Action layer (rclone-backed copy/move), dry-run, progress, audit log |
| Phase 4 | Drag-and-drop UI, undo log, conflict resolution UI, batch actions |
| Phase 5 | CLI companion tool, optional Syncthing-based background sync toggle |

## 12. Success Metrics
- Locate any file's location in under 5 seconds via search.
- Zero unintended data loss (measured via audit log + undo usage).
- Re-scan time under 30 seconds for 50k unchanged files (incremental hashing working).
- 100% of actions available via API achieve parity with UI.

## 13. Open Questions
- Scheduled vs. strictly manual re-scans — confirm default interval if scheduled.
- Should folders be a first-class sync unit alongside individual files?
- Native desktop app (Electron/Tauri) vs. browser dashboard — decide based on OS integration needs (drag-drop from real file explorer).
