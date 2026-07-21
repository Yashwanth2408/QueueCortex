# QueueCortex

A personal ticket-tracker and analytics dashboard for L2 support agents working Trinity tickets. Syncs from Trinity (via MCP) into a local SQLite database, then gives you a fast dashboard, full open/close/reopen history per ticket, and day/month/year performance analytics.

## Architecture

- **Backend**: FastAPI + SQLAlchemy (async) + SQLite, in `backend/`. Talks to Trinity over MCP (streamable HTTP), backfills full ticket history on first run, then polls incrementally every N minutes (configurable) plus a manual "Sync now".
- **Frontend**: React + Vite + TypeScript + shadcn/ui + Recharts + TanStack Query, in `frontend/`.

## Running it

**Backend** (from `backend/`):
```
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
First time setup: `py -3.11 -m venv .venv`, then `.venv\Scripts\python.exe -m pip install -r requirements.txt`, copy `.env.example` to `.env` and fill in `TRINITY_MCP_TOKEN`, then `.venv\Scripts\python.exe -m alembic upgrade head`.

**Frontend** (from `frontend/`):
```
npm install
npm run dev
```
Opens on http://localhost:5173, proxying `/api` to the backend on port 8000.

On first run, trigger a full backfill from the Dashboard's "Sync now" button (or `POST /api/v1/sync/run {"mode":"full"}`) to pull your full ticket history from Trinity.

## Key ideas

- `tickets` is a cached current-state row; `ticket_events` is the append-only source of truth pulled from Trinity's audit trail; `status_transitions` has **one row per status-change event**, not per ticket — so a ticket closed yesterday and reopened+reclosed today counts toward *today's* close tally automatically, with no special-case code.
- Tag → Type mapping (Settings page) is user-editable and drives ticket categorization (Deployment/Billing/Refund/etc.) since Trinity tags are freeform, not a fixed type field.
- Aging/SLA highlighting and "needs attention" are explicit local heuristics — Trinity has no real SLA/priority field.
