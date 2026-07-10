# SetSync — Cross-PC Inventory & Set-Logic Sync

SetSync is a tool designed to synchronize, analyze, and consolidate file estates across multiple devices using rolling-delta block transfer protocol, automated scanning, and semantic intelligence.

---

## Technical Architecture

- **Backend**: FastAPI backend serving core logic, database storage (SQLite/Postgres), and block transfer service.
- **Frontend**: React + Vite SPA using TypeScript and styling via Tailwind or custom CSS.
- **Agent**: Python CLI that runs on individual PCs, indexes file systems, watches for modifications via `watchdog`, and communicates with the backend.

---

## Quickstart

### 1. Docker Compose (Recommended)

Spins up the core backend service (port `8000`) and the React Web UI (port `3000`):

```bash
docker compose up --build
```

Access the Web UI at: [http://localhost:3000](http://localhost:3000). The default authentication token is `setsync_secret_token_123`.

### 2. Local Setup (Without Containers)

#### A. Seed Simulation Folders
Before running, you can seed two mock PC directories (`./test_pc_a` and `./test_pc_b`) to test sets and sync interactions locally:
```bash
python seed_test_dirs.py
```

#### B. Start Core Backend Server
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### C. Run Inventory Agent CLI
You can packaging-install the agent using `pip`:
```bash
cd agent
pip install -e .
# Or globally via pipx
pipx install .
```

Scan a directory:
```bash
setsync-agent scan --pc A --root ./test_pc_a
setsync-agent scan --pc B --root ./test_pc_b
```

Watch a directory in real-time:
```bash
setsync-agent watch --pc A --root ./test_pc_a
```

#### D. Start Frontend Dev Server
```bash
cd frontend
npm install
npm run dev
```

---

## Running the Test Suite

Run unit and integration tests inside the `backend` folder:

```bash
cd backend
python -m pytest -v
```

To run with coverage gate and term details:
```bash
python -m pytest --cov=app --cov-report=term-missing tests/
```
