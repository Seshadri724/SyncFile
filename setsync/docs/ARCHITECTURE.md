# SetSync — Architecture & System Design

**Version:** 1.0 · **Date:** 2026-07-07
Covers: current state (as-built), target architecture per roadmap phase, data
model evolution, transfer protocol design, AI-layer design, and security model.

---

## 1. Current Architecture (as-built, v2 branch)

```
┌─────────────────────────── ONE MACHINE (simulation) ───────────────────────────┐
│                                                                                 │
│  agent/ (CLI, click)                 backend/ (FastAPI)          frontend/      │
│  ┌──────────────┐   HTTP POST        ┌────────────────────┐     ┌───────────┐  │
│  │ scanner.py   │  /inventory  ───►  │ routers/           │◄────│ React +   │  │
│  │ watcher.py   │                    │  inventory, sets,  │ REST│ Vite      │  │
│  │ uploader.py  │                    │  actions, audit    │     │ App.tsx   │  │
│  │ db.py (cache)│                    ├────────────────────┤     └───────────┘  │
│  └──────────────┘                    │ services/          │                    │
│   scans ./test_pc_a                  │  set_engine (SQL)  │                    │
│   and   ./test_pc_b                  │  action_service    │                    │
│   as "PC A"/"PC B"                   │  audit_service     │                    │
│                                      ├────────────────────┤                    │
│                                      │ transfer/          │                    │
│                                      │  local, rclone,    │──── direct fs ops  │
│                                      │  delta_sync        │     on both roots  │
│                                      ├────────────────────┤                    │
│                                      │ SQLite (async)     │                    │
│                                      └────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**What's already good (keep):**
- Clean layering: routers → services → models; transfer strategies behind `base.py`
- Dry-run / undo / audit primitives exist (`action_service`, `undo_record`, `audit`)
- Rolling-hash delta sync (Adler-32 + SHA-256, rsync-style) with unit tests
- Watchdog-based real-time agent watcher

**Structural limits (what the roadmap fixes):**
| Limit | Where | Fix phase |
|---|---|---|
| Exactly 2 sources, hardcoded `'A'`/`'B'` in SQL | `set_engine.py` | 1 |
| Backend performs fs ops directly → both roots must be local | `action_service`, `transfer/local.py` | 1 |
| `compute_delta` reads whole file into memory | `delta_sync.py` | 0 |
| `NOT IN` subqueries, no indexes, no pagination | `set_engine.py` | 0 |
| CORS `*`, partial token coverage, `.env` in git | `main.py`, repo | 0 |

---

## 2. Target Architecture (Phase 1+)

```
   Machine 1 (laptop)          Machine 2 (NAS)            Cloud (Drive/S3)
  ┌────────────────┐         ┌────────────────┐         ┌──────────────┐
  │ SetSync Agent  │         │ SetSync Agent  │         │  (no agent)  │
  │ - scan/watch   │         │ - scan/watch   │         └──────▲───────┘
  │ - job executor │         │ - job executor │                │ rclone
  │ - delta engine │         │ - delta engine │                │
  └───────┬────────┘         └───────┬────────┘         ┌──────┴───────┐
          │ HTTPS + agent key        │                   │ RcloneRunner │
          │  inventory push,         │                   │ (coordinator │
          │  job poll/WebSocket,     │                   │  -side)      │
          │  block relay             │                   └──────┬───────┘
          ▼                          ▼                          │
  ┌─────────────────────────────────────────────────────────────┴──────┐
  │                    COORDINATOR (FastAPI)                            │
  │  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐ │
  │  │ Sources  │ │ Set Engine│ │ Analysis │ │ Jobs &  │ │ Policy   │ │
  │  │ registry │ │ (N-source)│ │ dedupe,  │ │ Plans   │ │ Engine   │ │
  │  │ + auth   │ │           │ │ semantic │ │ engine  │ │          │ │
  │  └──────────┘ └───────────┘ └──────────┘ └─────────┘ └──────────┘ │
  │  ┌──────────────────────────────────────────────────────────────┐ │
  │  │            SQLite (solo mode)  /  Postgres (team mode)       │ │
  │  └──────────────────────────────────────────────────────────────┘ │
  └───────▲──────────────────────▲─────────────────────────▲──────────┘
          │ REST /v1             │ REST /v1                 │ REST /v1
  ┌───────┴────────┐    ┌────────┴─────────┐    ┌───────────┴──────────┐
  │  React Web UI  │    │   MCP Server     │    │  AI Orchestrator     │
  │  sources, sets,│    │  (FastMCP shim)  │    │  (Claude tool-use:   │
  │  wizard, plans │    │  Claude Desktop, │    │  NL query, plans,    │
  │  approval view │    │  any MCP agent   │    │  conflict reasoning) │
  └────────────────┘    └──────────────────┘    └──────────────────────┘
```

**Core principle: the REST API is the only door.** UI, MCP server, and AI
orchestrator are all peer clients. AI gets no privileged path — same auth,
same policy engine, same audit.

### Component responsibilities

| Component | Owns | Never does |
|---|---|---|
| **Agent** | Scanning, hashing, watching, executing fs ops on *its own* machine, delta encode/decode, block serving | Talking to other agents directly (v1), making policy decisions |
| **Coordinator** | Source registry, inventory DB, set logic, job orchestration, plans, policy, audit, block relay | Touching any filesystem except its own working dir |
| **MCP server** | Translating MCP tool calls → REST | Bypassing REST; holding state |
| **AI orchestrator** | NL→query translation, plan drafting, conflict reasoning | Executing anything without a dry-run-backed, policy-checked, (human-approved) plan |

---

## 3. Data Model Evolution

### Phase 1 target schema

```sql
sources          (id uuid PK, name, kind ENUM(device,remote), roots JSON,
                  agent_key_hash, status, last_seen_at, created_at)

file_records     (id PK, source_id FK→sources, relative_path, size_bytes,
                  hash_sha256, mtime, scanned_at,
                  UNIQUE(source_id, relative_path))
                  -- INDEX (source_id, relative_path), INDEX (hash_sha256)

transfer_jobs    (id uuid PK, kind ENUM(copy,move,delete), file_relative_path,
                  src_source_id, dst_source_id, state ENUM(pending,assigned,
                  running,done,failed,cancelled), block_cursor, bytes_done,
                  plan_id FK NULL, error, created_at, updated_at)

action_records   (id, job_id FK, action_type, triggered_by ENUM(ui,mcp,agent,ai),
                  dry_run_token, executed_at, ...)       -- extends existing
undo_records     (id, action_id FK, reverse_op JSON, expires_at, ...)  -- existing
audit_log        (id, actor, actor_kind, action_id, plan_id, detail, ts) -- existing

-- Phase 4
plans            (id uuid PK, goal_text, author ENUM(human,ai), state ENUM(draft,
                  approved,executing,done,failed,partially_undone),
                  approved_by, approved_at, checkpoint JSON, created_at)
plan_items       (id, plan_id FK, seq, action JSON, dry_run_snapshot JSON,
                  rationale TEXT, state)
policies         (id, org_id, yaml TEXT, version, active)

-- Phase 4 semantic
file_signals     (file_record_id FK, phash BIGINT NULL, embedding BLOB NULL,
                  content_kind, computed_at)   -- computed BY AGENTS locally

-- Phase 5
orgs, users, memberships (RBAC)
```

### Set-engine rewrite (Phase 1)
Replace literal `'A'`/`'B'` SQL with parameterized pairwise queries
(`:src_x`, `:src_y`) + estate-wide views:

```sql
-- "unique data risk": hash exists on exactly one source
SELECT hash_sha256, MIN(source_id) AS only_on
FROM file_records GROUP BY hash_sha256 HAVING COUNT(DISTINCT source_id) = 1;
```

Use `NOT EXISTS` (correlated) instead of `NOT IN`; paginate everything.

---

## 4. Transfer Protocol Design (Phase 1)

### Job lifecycle
```
UI/MCP/AI ─► POST /actions (dry_run) ─► dry-run token
          ─► POST /actions (execute, token) ─► policy check ─► transfer_job(pending)

dst agent polls /jobs ─► assigned ─► running:
   1. dst: has old version? → compute block signatures → upload to coordinator
   2. src agent: fetch signatures → stream delta ops (copy refs + literal data)
      → coordinator relays chunks → dst applies to TEMP file
   3. dst: verify full-file SHA-256 == expected → atomic rename over target
   4. job: done → action_record + undo_record + audit row
```

### Design decisions & rationale
| Decision | Choice | Why |
|---|---|---|
| Agent connectivity | Agents dial **out** to coordinator (poll/WebSocket) | No inbound firewall holes on user machines — critical for consumer adoption |
| Data path v1 | Relay through coordinator | Simple, works behind NAT; direct agent↔agent (brokered) is a v2 optimization |
| Integrity | Whole-file SHA-256 verify **before** atomic rename | A failed transfer can never corrupt the destination |
| Resumability | Persist `block_cursor` per job; chunks idempotent | `kill -9` safe (Checkpoint Gate 1 requirement) |
| Delta engine | Streaming rolling Adler-32 window + SHA-256 block confirm | Fixes O(filesize) memory; standard rsync approach |
| Undo for move/delete | Trash-style holding area on the owning agent (`.setsync/trash/<action_id>`), purged with undo expiry | True reversibility without coordinator storing file content |

---

## 5. AI Layer Design (Phases 3–4)

### MCP server (Phase 3)
- FastMCP app, stdio (Claude Desktop) + streamable HTTP transports.
- **Plan-before-act enforced in the tool contract**: `execute_action` requires a
  `dry_run_token` returned by a prior `dry_run_action` call for the *same*
  parameters (token = hash of params + TTL). An agent physically cannot skip preview.
- Read tools are cheap and unrestricted; mutating tools run through the same
  policy engine and are audited with `actor_kind=mcp`.

### NL query (Phase 3)
```
user question ─► Claude (Haiku-class) with ONE tool: emit_query(filters)
             ─► validated against filter schema ─► set engine executes
             ─► rows + generated filter shown to user (transparency)
```
LLM sees the *schema*, never file contents. Cost ≈ nothing; latency < 2s.

### Agentic plans (Phase 4)
```
goal ─► Claude (Sonnet-class) tool-use loop over READ tools only
     ─► drafts plan_items (each = dry-run snapshot + rationale)
     ─► policy engine validates every item (reject → agent revises)
     ─► plan(draft) surfaces in UI as reviewable diff
     ─► human approves ─► checkpointed executor runs items sequentially
     ─► any failure: halt, offer reverse-order undo of completed items
```
The AI **drafts**; the policy engine **constrains**; the human **approves**;
the job engine **executes**. Four separate authorities — that separation is
the safety story and the moat.

### Conflict reasoning (Phase 4)
Opt-in per file/batch. Agents extract *bounded* evidence locally (text diff
head ≤ 4 KB, EXIF, size/mtime) and upload only that. Claude returns
`{recommendation, confidence, evidence[]}` rendered verbatim in the UI.

### Semantic dedupe (Phase 4)
Computed **on agents** (privacy + no upload cost): pHash for images,
MiniLM-class local embeddings for text. Coordinator only clusters signals.
API-based embedding is an explicit opt-in.

---

## 6. Security Model

| Layer | Mechanism |
|---|---|
| Agent ↔ Coordinator | HTTPS; per-source bearer key (hash stored); keys revocable in UI |
| UI/MCP ↔ Coordinator | Session token (solo mode: local-only bind by default); OIDC in Phase 5 |
| Authorization | Policy engine on every mutation; RBAC in Phase 5 |
| Data at rest | Coordinator stores **metadata only** (paths, hashes, sizes) — file *content* transits as relay chunks, never persisted; trash areas live on agents |
| AI boundary | LLM receives schema + bounded evidence, never bulk content; every AI-triggered action tagged `actor_kind=ai` in audit |
| Secrets | Env-only; `.env` never committed; agent keys shown once at registration |
| Supply chain | Pinned deps, lockfiles, CI audit (pip-audit / npm audit) |

### Trust invariants (enforced in code, tested in CI)
1. No mutation without a dry-run record.
2. No deletion of a hash's last copy without `force=true` (checked server-side).
3. Every mutation produces an undo record before it is acknowledged.
4. Destination writes are temp-file + verify + atomic rename, always.

---

## 7. Scaling Path

| Estate size | Configuration |
|---|---|
| ≤ 100k files, 1 user | SQLite, single process, everything local (default forever) |
| ≤ 1M files, small team | SQLite→Postgres, coordinator on a NAS/VPS, indexes + keyset pagination |
| 10M+ files, MSP/enterprise | Postgres + read replicas; hash-partitioned `file_records`; job queue → Redis/ARQ workers; block relay moved to object storage presigned flow |

**Hashing at scale (agent side):** size+mtime prefilter (only re-hash changed
files — the agent cache DB already supports this), xxHash3 fast pass with
SHA-256 confirmation on candidate matches, io-throttled background hashing.

---

*Companion docs: [PRD.md](PRD.md) · [ROADMAP.md](ROADMAP.md) · [RESOURCES.md](RESOURCES.md)*
