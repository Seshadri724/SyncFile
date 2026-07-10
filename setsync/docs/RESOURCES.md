# SetSync — Build Resources & Reference Guide

**Version:** 1.0 · **Date:** 2026-07-07
Everything to reach for while executing [ROADMAP.md](ROADMAP.md), organized by phase.

---

## Core Stack (already in use — deepen these)

| Tech | Used for | Key docs |
|---|---|---|
| **FastAPI** | Coordinator API | fastapi.tiangolo.com — study: dependencies, `BackgroundTasks`, WebSockets, lifespan, `APIRouter` versioning |
| **SQLAlchemy 2.x async** | ORM + raw SQL | docs.sqlalchemy.org — study: async sessions, hybrid raw-SQL/ORM, connection pooling for Postgres |
| **Alembic** | Schema migrations (Phase 1 is a big one) | alembic.sqlalchemy.org — autogenerate + hand-written data migrations |
| **Pydantic v2** | Schemas, settings | docs.pydantic.dev — `pydantic-settings` for env config |
| **Click** | Agent CLI | click.palletsprojects.com |
| **Watchdog** | Agent fs events | github.com/gorakhargosh/watchdog — debouncing patterns matter |
| **React + Vite + TS** | Frontend | Add **TanStack Query** (server state) + **TanStack Table** (virtualized 100k-row tables) — both are made for exactly this UI |
| **rclone** | Cloud remotes + transfers | rclone.org/docs — `lsjson`, `hashsum`, `copyto`, `--use-json-log`; also `rclone rcd` (remote-control daemon API) as an alternative to shelling out |

---

## Phase 0 — Hardening

- **Hypothesis** (property-based testing) — hypothesis.readthedocs.io.
  The delta round-trip invariant (`apply(delta(src, sig(dst)), dst) == src`) is a
  textbook Hypothesis use case; let it generate adversarial binary inputs.
- **pytest-asyncio**, **pytest-cov** — async test + coverage gates.
- **GitHub Actions** — docs.github.com/actions; matrix-test Windows/macOS/Linux
  early (path handling *will* differ).
- **git-filter-repo** — github.com/newren/git-filter-repo — purge committed `.env`
  files from history before the repo goes public.
- **The rsync algorithm paper** — Tridgell & Mackerras, 1996
  (rsync.samba.org/tech_report) — the canonical reference for the rolling-window
  streaming rewrite of `delta_sync.py`. Read §3–4.
- **SQLite performance** — sqlite.org/queryplanner + `EXPLAIN QUERY PLAN`;
  covering indexes for the set queries; WAL mode for concurrent reads.

## Phase 1 — N-Device Foundation

- **WebSockets in FastAPI** or long-polling — for the agent job channel.
  Alternative worth evaluating: **Server-Sent Events** (simpler, proxy-friendly)
  for coordinator→agent signaling with plain POST for agent→coordinator.
- **Syncthing's Block Exchange Protocol spec** — docs.syncthing.net/specs —
  don't copy it, but it's the best prior art for block-level device sync
  (block size choices, integrity, NAT traversal reasoning).
- **restic's design doc** — restic.readthedocs.io/en/stable/100_references —
  excellent content-addressed-storage and atomicity patterns.
- **tenacity** — retry with backoff for agent networking.
- **httpx** — async HTTP client for the agent (replace `requests` if present).
- **platformdirs** — correct per-OS agent data/cache dirs (`%LOCALAPPDATA%`, `~/.local/share`).
- **keyring** — store agent keys in the OS credential store, not plaintext.
- Atomic write pattern: write temp in same directory → fsync → `os.replace()`
  (atomic on Windows + POSIX).

## Phase 2 — Analysis & Launch

- **rclone `lsjson --hashsum`** — remote inventory with hashes where the backend
  supports them (S3 ETag caveats: multipart uploads ≠ MD5 — verify per-backend).
- **WeasyPrint** or **Typst** — Markdown/HTML → PDF for audit certificates.
- **Recharts** or plain SVG — summary strip / treemap visuals in the UI.
- Launch channels: **r/DataHoarder**, **r/selfhosted**, **Hacker News (Show HN)**,
  **Product Hunt**; study how **Czkawka** and **rclone** run their GitHub
  communities (issues templates, discussions).
- Licensing decision reading: **AGPL vs MIT + commercial** — study Plausible
  (AGPL + hosted) and Sentry (BSL) models before choosing.

## Phase 3 — MCP + NL Query

- **MCP Python SDK / FastMCP** — github.com/modelcontextprotocol/python-sdk —
  server quickstart, stdio + streamable HTTP transports, tool annotations
  (`readOnlyHint`, `destructiveHint` — use them; Claude respects them).
- **MCP spec** — modelcontextprotocol.io — especially tool design and security
  best-practices pages.
- **Claude API** — docs.anthropic.com — tool use (forced tool choice for the
  NL→filter translation), structured outputs. Model choice: Haiku-class for
  query translation (cheap, fast), Sonnet-class for plan drafting (Phase 4).
- **Anthropic cookbook** — github.com/anthropics/anthropic-cookbook — tool-use
  and agent-loop patterns.
- Registry/distribution: MCP server registries + a copy-paste
  `claude_desktop_config.json` snippet in the README.
- Build the **eval set first**: 20 NL questions + expected filters as a pytest
  fixture; run on every prompt change.

## Phase 4 — Agentic + Semantic

- **Claude agentic tool-use loop** — Anthropic docs "building agents" +
  cookbook agent examples; the plan-draft loop is a read-only-tools agent.
- **imagehash** (pHash/dHash) — github.com/JohannesBuchner/imagehash — image
  near-duplicates; hamming-distance threshold ~≤ 8 for "same image."
- **sentence-transformers** — sbert.net — `all-MiniLM-L6-v2` runs fine on CPU
  agents for doc embeddings; ONNX export if you need it lighter.
- **sqlite-vec** — github.com/asg017/sqlite-vec — vector similarity inside
  SQLite; avoids a vector-DB dependency for solo mode.
- **Stripe** — stripe.com/docs/billing — or **Lemon Squeezy / Paddle** (merchant
  of record = they handle global sales tax; usually the right call for a solo dev).
- Policy engine: keep it a **simple YAML rules evaluator you write yourself**
  (~200 lines); OPA/Cedar are overkill until enterprise asks.

## Phase 5 — Scale & Enterprise

- **Postgres** + **asyncpg**; keyset pagination (use `id > :last` not OFFSET).
- **ARQ** or **Dramatiq** — async job queues when in-process jobs stop scaling.
- **OpenTelemetry + Sentry** — tracing + error tracking.
- **Authlib / OIDC** — SSO for enterprise.
- Packaging: **PyInstaller** or **Briefcase** (agent binaries), **WiX** (Windows
  MSI), notarytool (macOS), **Homebrew tap**, **winget manifest**, **Helm chart**.
- Compliance vocabulary reading: SOC 2 CC-series controls, GDPR Art. 30 records —
  so governance reports use the words auditors expect.

---

## Prior Art Worth Studying (not copying)

| Project | Steal the lesson |
|---|---|
| **Syncthing** | Device-ID trust model, block protocol, how OSS trust is earned |
| **rclone** | Backend abstraction layer, community-driven backend growth |
| **restic** | Content-addressed integrity, repository atomicity |
| **Czkawka** | What a great duplicate-finder UX looks like (and its single-machine ceiling — your opening) |
| **FreeFileSync** | Two-pane compare UX conventions users already know |
| **Tailscale** | Gold standard for "agents dial out, zero firewall config" onboarding and for docs tone |

## Recurring Time Sinks — Budget for These

1. **Windows vs POSIX paths** — normalize `relative_path` to forward slashes at
   ingest; test with unicode + >260-char Windows paths (`\\?\` prefix).
2. **File locking on Windows** — can't rename over an open file; retry loops needed.
3. **mtime semantics** — FAT32 2-second granularity, timezone-naive NAS mtimes;
   never trust mtime alone, it's only a prefilter.
4. **Long-running scans** — always incremental (agent cache), always resumable,
   always io-throttled.
5. **rclone backend quirks** — hash availability differs per backend; feature-detect.

---

*Companion docs: [PRD.md](PRD.md) · [ROADMAP.md](ROADMAP.md) · [ARCHITECTURE.md](ARCHITECTURE.md)*
