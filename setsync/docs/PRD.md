# SetSync — Product Requirements Document (PRD)

**Version:** 1.0 · **Date:** 2026-07-07 · **Status:** Draft
**Owner:** Seshadri · **Repo:** `setsync`

---

## 1. Product Vision

**SetSync is a trustworthy agent for your file estate** — it shows you exactly what
lives where across all your devices and cloud storage, finds duplicates and gaps,
and lets you (or an AI agent acting on your behalf) reconcile everything with
dry-run previews, one-click undo, and a full audit trail.

> Positioning: **NOT** another sync tool. Syncthing/Resilio/GoodSync own
> "keep folders identical." SetSync owns **reconciliation and consolidation** —
> "know exactly what's where *before* anything moves."

### One-line pitch
*"The file agent you can trust with delete."*

---

## 2. Problem Statement

People and organizations accumulate files across laptops, desktops, NAS boxes,
external drives, and cloud accounts. When they need to **merge, migrate, clean up,
or decommission**, existing tools fail them:

| Pain | Today's broken answer |
|---|---|
| "What exists only on my old laptop?" | Manual eyeballing, no tool answers this |
| "Which of these 4 drives has unique data?" | Blind copy-everything, duplicates explode |
| "Same path, different content — which do I keep?" | Sync tools force a blind choice |
| "Prove nothing was lost when we wiped that machine" | No audit trail exists |
| "Can an AI safely clean this up for me?" | Nobody trusts AI near their files |

Blind sync tools *terrify* exactly the users who need this most: they want
**visibility, preview, reversibility, and proof** — SetSync's core primitives.

---

## 3. Target Users & Personas

### P1 — The Consolidator (primary, consumer)
Merging an old laptop into a new one, or 4 external drives into a NAS.
Technical enough to install a tool; motivated by fear of losing data.
*Communities: r/DataHoarder, homelab, NAS forums.*

### P2 — The Media Professional
Photographer / videographer with SD-card dumps and RAW libraries scattered
across drives. Needs hash-level dedupe and "safe to delete" confidence.

### P3 — The IT Operator / MSP (primary, revenue)
Decommissions and migrates machines for a living. Needs audit-grade reports:
"everything on this machine exists elsewhere; here's the certificate."

### P4 — The Agent Builder (strategic)
Uses Claude Desktop / MCP-capable agents. Wants their AI to answer
"what's not backed up?" and act on it safely. Reached via the MCP ecosystem,
not via downloads.

### P5 — The Compliance Team (enterprise, later)
GDPR / SOC 2 / offboarding. "Where does PII live across our endpoints?
Which devices hold data that exists nowhere else?"

---

## 4. Goals & Non-Goals

### Goals
1. Inventory N devices + cloud remotes into one queryable set-logic view.
2. Every mutating action is **previewable (dry-run), reversible (undo), and audited**.
3. Expose the whole capability surface to AI agents via **MCP**.
4. AI-native features on top: natural-language queries, reasoned conflict
   resolution, semantic (near-)duplicate detection, agentic consolidation plans.
5. Audit-grade reporting for migration/decommission workflows.

### Non-Goals
- ❌ Continuous real-time bidirectional sync (Syncthing's territory; we do
  scheduled/on-demand reconciliation).
- ❌ File hosting / storage provider (we coordinate, we don't store content).
- ❌ Mobile-first clients (v1 is desktop/server; mobile is inventory-read-only later).
- ❌ Versioned backup with history (we reconcile current state; point users to
  restic/Borg for backup).

---

## 5. Feature Requirements

### P0 — Foundation (must ship before anything else matters)
| ID | Feature | Requirement |
|---|---|---|
| F-01 | N-source inventory | Replace hardcoded `A`/`B` with registered `sources` (device or remote), each with id, name, type, root(s), last-seen |
| F-02 | Networked agents | Agents run on *their own machines*, authenticate to the coordinator, push inventory, and **execute transfers locally** (coordinator never needs filesystem access to remote roots) |
| F-03 | Real auth | Per-agent API keys/tokens; scoped; revocable. Lock down CORS |
| F-04 | Pairwise + estate-wide set views | Union / intersection / only-X / conflicts computed for any pair, plus "exists on exactly one source" estate-wide |
| F-05 | Scalable engine | 1M+ file records: indexed columns, `NOT EXISTS` instead of `NOT IN`, paginated APIs |
| F-06 | Streaming delta transfer | Fix in-memory `compute_delta`; stream windows; resumable transfers |

### P1 — Differentiators
| ID | Feature | Requirement |
|---|---|---|
| F-10 | Cloud remotes as sources | rclone-backed inventory (Google Drive, S3, OneDrive, …) — compare local vs cloud |
| F-11 | Duplicate analyzer | Exact-hash duplicate groups within and across sources; "space reclaimable" metric |
| F-12 | Safe-to-delete engine | A file is flagged safe only if its hash exists on ≥N other sources (policy-configurable) |
| F-13 | Consolidation wizard | Source→destination flow: report → conflict review queue → execute → audit certificate (exportable PDF/MD) |
| F-14 | Stale/orphan report | Untouched >N years, exists on exactly one source (data-loss risk view) |

### P2 — AI layer
| ID | Feature | Requirement |
|---|---|---|
| F-20 | **MCP server** | Tools: `list_sources`, `query_files`, `compare_sources`, `find_duplicates`, `dry_run_action`, `execute_action`, `undo_action`, `get_audit_log`. Mutations gated behind dry-run + approval |
| F-21 | NL query | Chat box → structured query against existing filters/set views (LLM translates, engine executes — LLM never touches raw file content for queries) |
| F-22 | Reasoned conflict resolution | For a conflict pair: diff docs, compare EXIF/metadata, recommend keep/merge **with shown evidence**; user approves |
| F-23 | Semantic dedupe | Perceptual hash (images) + embeddings (docs) near-duplicate groups, with "what differs" explanations |
| F-24 | Agentic consolidation | Goal in plain English → plan built from dry-runs → human approval gate → checkpointed execution → all steps undoable |

### P3 — Enterprise
| ID | Feature | Requirement |
|---|---|---|
| F-30 | Postgres + multi-tenant | Org/user model, RBAC |
| F-31 | Governance reports | PII classification flags, unique-data risk report, decommission certificates |
| F-32 | Policy engine | Declarative rules: "never delete unique data," "never touch /work," approval thresholds |
| F-33 | Fleet dashboard | MSP view across client machines |

---

## 6. Trust & Safety Requirements (product law — every phase)

1. **No blind mutations.** Every copy/move/delete has a dry-run; destructive ops
   require explicit confirmation (human or approval-gated agent).
2. **Everything is undoable** within the retention window; undo records survive restarts.
3. **Everything is audited**: who/what (human vs agent), when, why (plan reference).
4. **Unique-data protection is default-on**: refuse to delete the last copy of any
   hash unless the user overrides with an explicit flag.
5. **AI acts through the same API as humans** — same dry-run, same policy engine,
   same audit. No privileged AI path.

---

## 7. Success Metrics

| Phase | Metric | Target |
|---|---|---|
| Foundation | 3+ real devices reconciled end-to-end by external testers | 10 testers |
| Launch | GitHub stars / installs (open-core release) | 1k stars in 3 months |
| MCP | Weekly active MCP connections | 500 |
| Activation | % of new users completing one consolidation wizard run | 40% |
| Trust | Undo usage without data loss reports | 0 data-loss incidents |
| Revenue | Paid conversions (semantic dedupe / pro tier) | 2% of MAU |

---

## 8. Competitive Landscape

| Tool | What it owns | Why SetSync wins the reconciliation use case |
|---|---|---|
| Syncthing | Free continuous P2P sync | No analytical view, no dedupe, no audit, no dry-run review |
| rclone | CLI cloud transfer Swiss-army knife | Power-user CLI only; no cross-device set view; we *embed* it |
| FreeFileSync | Two-folder visual compare | Two folders on one machine only; no agents, no AI, no audit |
| GoodSync/Resilio | Commercial sync | Sync-first; same blind spots |
| TreeSize/WinDirStat | Single-disk space analysis | One machine, no actions, no cross-device |
| Czkawka/dupeGuru | Local duplicate finders | One machine, no estate view, no safe-execution harness |

**Moat:** the dry-run/undo/audit harness + set-logic engine is what makes the AI
layer *trustworthy* — competitors bolting AI onto sync tools won't have it.

---

## 9. Monetization

- **Open-core**: inventory, set views, pairwise reconcile, local transfers → free & open source (trust + distribution; how this category is won).
- **Pro (individual, ~$5–8/mo or one-time)**: cloud remotes, semantic dedupe, NL query, consolidation wizard exports.
- **Teams/MSP (~$20/seat/mo)**: fleet dashboard, governance reports, policy engine, decommission certificates.
- **Enterprise (custom)**: SSO, on-prem coordinator, compliance reporting, PII discovery.

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Data loss bug destroys trust permanently | Unique-data protection default-on; property-based tests on the action engine; staged rollout; undo everything |
| Scope creep into "sync tool" | Non-goals section is law; reconciliation-first |
| MCP spec churn | Thin adapter layer over the REST API; MCP is a facade, not the core |
| Hash cost on huge estates | Size+mtime prefilter, incremental hashing, xxHash fast-pass + SHA-256 confirm |
| LLM cost/misuse in AI tier | NL query compiles to structured filters (cheap); content-reading features are opt-in per file |
| Solo-dev bandwidth | Phased roadmap with hard checkpoints (see ROADMAP.md); each phase independently shippable |

---

## 11. Release Criteria (v1.0 public)

- [ ] 3+ sources (2 devices + 1 cloud remote) reconciled end-to-end
- [ ] 100k-file estate: all set views < 2s, UI paginated
- [ ] Zero-data-loss test suite green (including kill -9 mid-transfer → resume/undo)
- [ ] One-command install per platform (pipx / installer / Docker)
- [ ] MCP server published and usable from Claude Desktop
- [ ] README with demo GIF; docs site; consolidation-wizard demo video

---

*Companion docs: [ROADMAP.md](ROADMAP.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [RESOURCES.md](RESOURCES.md)*
