# SetSync — Phased Roadmap with Instructions & Checkpoints

**Version:** 1.0 · **Date:** 2026-07-07
Each phase is **independently shippable** and ends with a hard checkpoint gate —
do not start the next phase until every checkpoint passes. Estimates assume a
solo developer working part-time; halve them for full-time.

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5
Harden      N-Device    Analysis    MCP + NL    Agentic     Scale +
& Fix       Foundation  & Cloud     (AI v1)     (AI v2)     Enterprise
~2 wks      ~4-6 wks    ~4 wks      ~3 wks      ~5-6 wks    ongoing
```

---

## Phase 0 — Hardening & Foundations (~2 weeks)

**Goal:** fix everything that will break under real users *before* building on top.
No new features; pure debt payoff. Ships as an internal-quality release.

### Instructions
1. **Fix delta-sync memory blowup** — `backend/app/transfer/delta_sync.py`
   `compute_delta()` does `f.read()` on the whole source file. Rewrite as a
   streaming sliding window using Adler-32's rolling property (subtract the
   outgoing byte, add the incoming byte) so a 50 GB file uses O(block_size) memory.
   Add tests with multi-GB sparse files.
2. **Fix set-engine scalability** — replace `NOT IN (SELECT …)` with
   `NOT EXISTS` correlated subqueries; add indexes on
   `file_records(source_pc, relative_path)` and `file_records(hash_sha256)`.
   Add pagination (`limit`/`offset` or keyset) to `/sets` endpoints — the UI must
   never load 1M rows.
3. **Security pass** — restrict CORS to configured origins; make `verify_token`
   apply to *all* routers (audit which are unprotected); load secrets from env
   only; remove committed `.env` files from git history (`git filter-repo`),
   keep `.env.example` only; add `agent_cache.db` / `setsync.db` / `test_pc_*`
   to `.gitignore`.
4. **Test scaffolding** — pytest coverage gate in CI (GitHub Actions);
   property-based tests (Hypothesis) for delta encode→apply round-trip:
   `apply(delta(src, sig(dst)), dst) == src` for random binary inputs.
5. **Packaging baseline** — `pyproject.toml` for both `agent/` and `backend/`
   (installable via `pipx`), `docker-compose.yml` for backend+frontend,
   root `README.md` with quickstart.

### Checkpoint Gate 0 ✅
- [ ] Delta round-trip property tests pass incl. a 2 GB file under 200 MB RSS
- [ ] 500k synthetic file records: every set view responds < 2s
- [ ] No secrets or DB files tracked in git; CI green on every push
- [ ] `pipx install ./agent && docker compose up` gives a working system from a clean clone

---

## Phase 1 — N-Device Foundation (~4–6 weeks) ⚠️ THE BIG ONE

**Goal:** kill the hardcoded A/B two-machine simulation. Agents run on their own
machines over the network and execute transfers themselves. Everything later
stacks on this.

### Instructions
1. **Schema migration (Alembic)** —
   - New `sources` table: `id (uuid), name, kind (device|remote), roots[],
     agent_key_hash, last_seen_at, status`.
   - `file_records.source_pc` → `source_id (FK)`; migrate existing A/B rows.
   - Rewrite `set_engine.py` queries to be **parameterized by (source_x, source_y)**
     instead of literal `'A'`/`'B'`; add estate-wide queries
     (`exists on exactly one source`, `exists on all sources`).
2. **Agent registration & identity** — `POST /sources/register` issues a
   long-lived agent key (hash stored server-side). Agent persists identity in its
   local DB. All agent calls authenticated per-source. Add `setsync-agent init`
   interactive setup to the CLI.
3. **Agent-executed transfer protocol** — the coordinator can no longer touch
   remote paths. Redesign actions as **jobs**:
   - Coordinator creates a `transfer_job` (file, src source, dst source, type).
   - Agents long-poll (`GET /jobs/poll`) or hold a WebSocket; the *destination*
     agent pulls blocks from the *source* agent **via the coordinator relay**
     (v1: relay through coordinator; v2 option: direct agent↔agent with
     coordinator-brokered auth).
   - Wire the Phase-0 streaming delta into this path: dst sends signatures →
     src computes delta → dst applies. Chunked, resumable (persist block cursor).
4. **Move dry-run/undo/audit to the job model** — dry-run asks the *agents*
   what would happen (they own the filesystems); undo records store enough to
   reverse on the owning agent; audit rows link to job ids.
5. **Frontend: source picker** — replace the A/B assumption in
   `frontend/src/App.tsx` & API client with a source registry, pair selector for
   set views, and a jobs/progress panel (poll or SSE).
6. **Delete `test_pc_a`/`test_pc_b` simulation path** — keep a `--simulate`
   dev flag that spins up two local agents as subprocesses instead.

### Checkpoint Gate 1 ✅
- [ ] 3 real machines (or 3 VMs/containers) registered as sources; inventories visible in one UI
- [ ] Copy + move + delete executed **by agents** across two machines, incl. delta transfer of a modified large file
- [ ] `kill -9` an agent mid-transfer → job resumes or cleanly fails + is undoable; no partial file left at destination path (write to temp, atomic rename)
- [ ] Undo works for actions executed on a *remote* agent
- [ ] Old A/B code paths deleted (grep for `source_pc`, `'A'`, `'B'` returns nothing)

---

## Phase 2 — Analysis Features & Cloud Remotes (~4 weeks)

**Goal:** the differentiators that make people *want* this — dedupe, safe-to-delete,
cloud comparison, and the consolidation wizard. First public open-source release
at the end of this phase.

### Instructions
1. **rclone remotes as sources** (F-10) — new `RcloneSource` implementation:
   `rclone lsjson --hashsum` to inventory a remote into `file_records`
   (kind=`remote`). Transfers to/from remotes shell out to `rclone copyto`.
   Remote sources have no agent; the coordinator (or a designated agent) runs rclone.
2. **Duplicate analyzer** (F-11) — `GET /analysis/duplicates`: group by
   `hash_sha256` having count > 1, within and across sources; compute
   *space reclaimable* = Σ size × (copies − 1). Add to summary strip + a
   dedicated UI tab with group expansion.
3. **Safe-to-delete engine** (F-12) — policy: hash must exist on ≥ N other
   sources (default 1). Endpoint returns per-file safety verdict + evidence
   (where the other copies live). **Hard block** in `action_service` on deleting
   a unique hash without `force=true`.
4. **Stale/orphan report** (F-14) — filters on mtime age + single-source
   existence; "data-loss risk" view.
5. **Consolidation wizard** (F-13) — a guided frontend flow wrapping existing
   primitives: pick src+dst → summary report (unique GB, duplicate GB, conflicts)
   → conflict review queue (keep A / keep B / keep both) → batch job execution
   with progress → exportable audit certificate (Markdown → PDF).
6. **Launch prep** — polish README (demo GIF), CONTRIBUTING.md, license (AGPL or
   MIT+paid-tier decision), publish to GitHub, post to r/DataHoarder / HN /
   Product Hunt with the wizard demo video.

### Checkpoint Gate 2 ✅
- [ ] Google Drive (or S3) remote inventoried and compared against a local device
- [ ] Duplicate analyzer correct on a seeded corpus with known duplicate structure
- [ ] Attempting to delete the last copy of a file is refused (test proves it)
- [ ] One external tester completes a real consolidation via the wizard, unassisted, and exports the certificate
- [ ] Public repo live; install-from-README works on Windows, macOS, Linux

---

## Phase 3 — MCP Server + Natural-Language Query (AI v1) (~3 weeks)

**Goal:** SetSync becomes a capability inside the agent ecosystem. Highest
leverage-per-effort phase.

### Instructions
1. **MCP server** (F-20) — new `mcp/` package using the official Python MCP SDK
   (FastMCP). Thin adapter over the REST API (never bypass it — same auth, same
   policy engine). Tools:
   - Read: `list_sources`, `query_files(filters)`, `compare_sources(x, y, view)`,
     `find_duplicates`, `get_summary`, `get_audit_log`
   - Mutate: `dry_run_action` (always available), `execute_action`
     (requires a prior dry-run token — enforce plan-before-act *in the tool
     contract*), `undo_action`
   - Transport: stdio for Claude Desktop; streamable HTTP for remote.
2. **NL query endpoint** (F-21) — `POST /query/natural`: Claude translates the
   question into your structured filter schema (view_type, q, size, age, sources)
   via a tool-use call; the set engine executes; the LLM never sees file contents.
   Add a chat box in the UI over the files table. Model: Haiku-class is enough —
   this is structured translation, keep it cheap.
3. **Docs for agents** — an `llms.txt` / MCP usage doc so agents discover
   capabilities and safety contracts.
4. **Publish** — MCP registry listing, Claude Desktop setup guide with copy-paste
   config, demo video: *"Claude, what's on my old laptop that isn't backed up
   anywhere?"*

### Checkpoint Gate 3 ✅
- [ ] From Claude Desktop: list sources, run a comparison, find duplicates — zero SetSync UI involvement
- [ ] `execute_action` via MCP is impossible without a matching prior dry-run (test proves it)
- [ ] NL query answers 9/10 questions from a 20-question eval set correctly (build the eval set first)
- [ ] MCP server listed publicly; setup guide verified on a clean machine

---

## Phase 4 — Agentic Consolidation & Semantic Features (AI v2) (~5–6 weeks)

**Goal:** the flagship — plan/approve/execute agentic workflows, reasoned
conflicts, semantic dedupe. This is the paid tier.

### Instructions
1. **Policy engine** (F-32, pulled forward) — declarative YAML rules evaluated
   before any job: `never_delete_unique: true`, `protected_paths: [...]`,
   `max_batch_delete: 100`, `require_approval_above_gb: 10`. Applied identically
   to human and AI callers.
2. **Plan objects** (F-24) — `POST /plans`: a plan = ordered list of intended
   actions, each backed by a dry-run snapshot. States:
   `draft → approved → executing → done/failed/partially-undone`. Plans are
   checkpointed (resume after crash) and *wholly undoable* (reverse-order undo).
3. **Agentic consolidation** — Claude (tool-use loop, Sonnet-class) takes a goal
   ("merge old-laptop into NAS, keep newest on conflict, never touch /work"),
   queries the estate, drafts a plan with per-item rationale, and presents it for
   **human approval in the UI** (diff-style review). Execution only after approval.
4. **Reasoned conflict resolution** (F-22) — for a conflict pair, an opt-in
   "analyze" button: agents upload both versions' *metadata + content preview*
   (text diff head, EXIF, sizes, mtimes) — never silently the full file; Claude
   returns a recommendation **with evidence shown**. Batch mode for the wizard's
   conflict queue.
5. **Semantic dedupe** (F-23) — new `analysis/semantic` worker:
   - Images: perceptual hash (`imagehash` / pHash) computed **by agents locally**,
     uploaded as metadata.
   - Docs/text: local embeddings (e.g. `sentence-transformers` on the agent, or
     API-based opt-in) + cosine clusters.
   - UI: near-duplicate groups with "what differs" explanation.
6. **Payments** — license key or Stripe-backed account gating Pro features
   (cloud remotes stay free-tier-limited to 1 remote, semantic dedupe & agentic
   plans are Pro).

### Checkpoint Gate 4 ✅
- [ ] End-to-end: NL goal → agent-drafted plan → human approves in UI → checkpointed execution → full plan undo restores prior state (test on a 10k-file corpus)
- [ ] Policy engine blocks a plan that violates `protected_paths` *authored by the AI* (red-team test)
- [ ] Conflict recommendation shows evidence and is correct on a 30-case eval set ≥ 85%
- [ ] Semantic dedupe finds resized-image and edited-doc pairs the hash engine misses
- [ ] First paying customer 💰

---

## Phase 5 — Scale & Enterprise (ongoing)

**Goal:** revenue depth. Consumer tool becomes top-of-funnel; MSP/compliance pays.

### Instructions
1. **Postgres migration** — SQLAlchemy already abstracts most of it; move raw
   SQL in `set_engine.py` to dialect-safe queries; Alembic migration path;
   SQLite remains the default for solo/local mode (keep it forever — it's a feature).
2. **Multi-tenancy + RBAC** (F-30) — orgs, users, roles (admin/operator/viewer);
   sources belong to orgs; SSO (OIDC) for enterprise.
3. **Fleet dashboard** (F-33) — MSP view: all client machines, last-seen,
   unique-data risk per machine, pending decommissions.
4. **Governance reports** (F-31) — PII classifier flags (filename/exif/content
   opt-in), unique-data risk report, decommission certificate generator
   (signed PDF: "all 48,211 files verified present elsewhere").
5. **Ops maturity** — structured logging, OpenTelemetry traces, error tracking
   (Sentry), backup/restore of the coordinator DB, versioned REST API (`/v1/`).
6. **Distribution depth** — signed installers (Windows MSI via WiX, macOS
   notarized pkg), Homebrew tap, winget, Docker Hub images, Helm chart for
   self-hosted coordinator.

### Checkpoint Gate 5 ✅ (rolling)
- [ ] One MSP running SetSync across ≥20 client machines
- [ ] 1M-file estate benchmark: inventory ingest < 10 min, views < 2s, on Postgres
- [ ] SOC 2-style audit export accepted by a real compliance reviewer
- [ ] MRR target per PRD §7

---

## Cross-Phase Rules

1. **Never break the trust invariants** (PRD §6) — every PR touching
   `action_service`, transfers, or plans needs a data-safety test.
2. **The REST API is the only door.** UI, MCP, and agents all go through it.
3. **Each phase ends with a tagged release** and updated docs — even Phase 0.
4. **Eval sets before AI features** — build the test questions/cases *first*
   (Phases 3–4), or you can't tell if the AI layer works.

*Companion docs: [PRD.md](PRD.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [RESOURCES.md](RESOURCES.md)*
