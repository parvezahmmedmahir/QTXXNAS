# QUANTUM X PRO

Enterprise-grade signal generation & license-gated trading UI/backend (Quantum X PRO).

This repository contains a Python backend (Flask) and a static frontend (index.html) that together implement a license-locked signal generation system with win-rate tracking, diagnostics, and license administration tools.

---

## Table of Contents

- Project Overview
- Key Features (summary)
- Project Architecture & File Map
- Requirements
- Quickstart — Step-by-step setup
- Configuration (.env and database)
- Database Modes (SQLite / PostgreSQL (Supabase))
- License system: concepts and admin tools
- Scripts and utilities (what they do + examples)
- API Reference: endpoints & examples
- Frontend usage & unlocking flow
- Diagnostics & troubleshooting
- Emergency repair & master keys
- Security & deployment notes
- Contribution & contact
- License

---

## Project Overview

Quantum X PRO is built as a local/static front-end (single-page app: `index.html`) that communicates with a Python Flask backend (`app.py`) for license validation, signal generation, telemetry, and win-rate tracking. The backend supports two database modes: local SQLite (default) or PostgreSQL (configured via `DATABASE_URL`), and includes multiple administration and diagnostic utilities.

Intended use-cases:
- License-protected access to trading/market signals
- Signal generation engines (fallback & advanced engines)
- Tracking signal outcomes and usage analytics
- Administering license keys and emergency recovery

---

## Key Features

- License gate with device-locking and categories (OWNER, USER, TRIAL)
- Dual-mode DB (SQLite for local, PostgreSQL for cloud/Supabase)
- Signal generation engine(s) with deterministic/fallback engines
- Win-rate tracking and signal outcome recording
- Silent user activity telemetry (optional)
- Admin utilities for generating and managing keys
- Health checks, diagnostics, and emergency repair scripts
- Static front-end UI with license input and market tickers

---

## Project Architecture & File Map (key files)

- `app.py` — Main Flask backend. Handles:
  - Serving `index.html` as static file
  - License validation (`/api/validate_license`, `/api/check_device_sync`)
  - Predict/signal generation (`/predict`)
  - Win-rate endpoints (`/api/win_rate`, `/api/track_outcome`)
  - Activity tracking (`/api/track_activity`)
  - DB initialization and dual-mode DB handling (SQLite / Postgres)
  - Engine selection and fallback
- `index.html` — Front-end single page application (UI, license gate, tickers)
- `engine/` — Engine package (placeholder for custom/enhanced engines)
- `admin_license_manager.py` — Interactive CLI for listing, creating, activating, blocking, resetting, and extending licenses.
- `setup_licenses.py` — Script to bulk-generate license keys and insert them into the DB.
- `check_status.py` — Status checks: WebSocket adapters, deterministic signal tests.
- `verify_all.py` — Verifies frontend assets, backend connectivity and basic integration tests.
- `final_diagnostic.py` — Runs a diagnostic suite checking .env, DB, and subsystems.
- `emergency_fix.py` — Emergency repair tool to insert master keys and fix common DB/key problems.
- `check_db_keys.py` — Utility to check a small sample of keys in the DB.
- `README.md` — (this file)
- `.env` — Not committed; used to configure environment variables (see Configuration)
- `requirements.txt` — (if present) Python dependency listing

---

## Requirements

Minimum:
- Python 3.9+ (tested on 3.10 / 3.11)
- pip
- For PostgreSQL mode: access to a Postgres-compatible DB (Supabase, managed Postgres, etc.)
- Common Python packages (Flask, flask-cors, python-dotenv, psycopg2-binary, requests). If `requirements.txt` is present, install from it.

Install core packages (if `requirements.txt` is not present):

Unix / Mac:
```bash
python -m pip install flask flask-cors python-dotenv requests psycopg2-binary
```

Windows (PowerShell):
```powershell
py -m pip install flask flask-cors python-dotenv requests psycopg2-binary
```

Note: On some systems compiling `psycopg2` may require system libraries; `psycopg2-binary` is usually easier for dev.

---

## Quickstart — Step-by-step setup

1. Clone repository
   ```bash
   git clone https://github.com/parvezahmmedmahir/quantum_x_pro.git
   cd quantum_x_pro
   ```

2. Create and activate virtual environment (recommended)
   ```bash
   python -m venv .venv
   source .venv/bin/activate    # macOS / Linux
   .venv\Scripts\activate       # Windows
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt   # if exists
   # or install manually:
   pip install flask flask-cors python-dotenv requests psycopg2-binary
   ```

4. Create `.env` file at repo root (see Configuration below for keys). Minimal example:
   ```
   FLASK_ENV=development
   DATABASE_URL=
   PORT=5000
   SECRET_KEY=supersecret
   ```

5. Initialize the database (app.py will auto-init on start). Optionally run scripts:
   - To create master keys in DB: `python setup_licenses.py`
   - To run admin menu: `python admin_license_manager.py`

6. Run backend:
   ```bash
   python app.py
   # or for production
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

7. Open front-end:
   - For local testing: open `index.html` in your browser (file://) or host it via a simple server:
     ```bash
     python -m http.server 3000
     # then open http://localhost:3000/index.html
     ```
   - Note: `app.py` serves JSON API at port configured (default 5000). Frontend expects API at `http://localhost:5000`.

---

## Configuration (.env and important variables)

Create `.env` in repo root. Key variables the app may read:

- `DATABASE_URL` — If present, the app uses PostgreSQL (psycopg2). Leave empty to use local SQLite `security.db`.
- `PORT` — Backend port (default 5000).
- `SECRET_KEY` — Flask secret / signing key used by the app.
- `ENABLE_ENHANCED_ENGINE` — optional flag for an enhanced engine (module import).
- Any other env vars referenced in `app.py` or other scripts — check the top of `app.py` and other scripts.

Important: Do not commit `.env` with secrets.

---

## Database Modes

1. SQLite (default)
   - File: `security.db` is created in repo root.
   - Good for local testing and development.

2. PostgreSQL (cloud / Supabase)
   - Set `DATABASE_URL` to a Postgres connection string (e.g. `postgres://user:pass@host:port/dbname`)
   - The app detects `DATABASE_URL` and uses Postgres tables with SERIAL / TIMESTAMP types.
   - Run `setup_licenses.py` or `app.py` to initialize tables if they do not exist.

Tables used (created by `init_db()` in `app.py`):
- `licenses` — license_key / category / status / device binding / expiry and timestamps
- `win_rate_tracking` — records of signals, direction, confidence, outcome, created_at
- `system_connectivity` — service heartbeat / status
- `user_sessions`, `user_activity` — telemetry and session tracking

---

## License System: concepts and admin tools

- Categories:
  - `OWNER` — full/owner access, typically not device-bound
  - `USER` — user license, typically locks to first device
  - `TRIAL` — limited-time trial license
- Statuses:
  - `PENDING`, `ACTIVE`, `BLOCKED` (implementation uses these as string statuses)

Admin tools:
- `setup_licenses.py` — generates keys and populates DB. Run to insert batches of OWNER/USER/TRIAL keys.
- `admin_license_manager.py` — interactive CLI for:
  - listing licenses
  - creating a new license
  - showing details
  - activating, blocking, resetting (unbind device)
  - extending expiry
- `check_db_keys.py` — sample check for keys present in DB.

Emergency & master keys:
- `emergency_fix.py` can insert master keys (`QXMASTER`, `ADMIN2026`, `TESTKEY01`, `TRIAL2026`) into the DB if DB is empty or corrupted. Use with caution.

---

## Scripts and utilities (what they do)

- `app.py` — main backend service
- `setup_licenses.py` — generate and insert keys into database
- `admin_license_manager.py` — manage licenses interactively
- `verify_all.py` — integration verification tests (checks assets, backend, signal generation)
- `check_status.py` — subsystem checks (WebSocket adapters, deterministic signals)
- `final_diagnostic.py` — full diagnostic run
- `emergency_fix.py` — repair DB and inject master keys
- `check_db_keys.py` — inspect sample keys in DB
- `engine/` — engines; optional enhanced engine may be importable depending on environment

Examples:
- Create sample keys:
  ```bash
  python setup_licenses.py
  ```
- Run admin tool:
  ```bash
  python admin_license_manager.py
  ```
- Run diagnostics:
  ```bash
  python final_diagnostic.py
  ```
- Quick verification:
  ```bash
  python verify_all.py
  ```

---

## API Reference (most-used endpoints)

Base: `http://localhost:5000`

- GET `/` or `/home` — serves `index.html` (static)
- GET `/test` — basic JSON status, example:
  - Response:
    ```json
    {
      "status": "online",
      "server": "Quantum X PRO",
      "db_mode": "postgres" // or "sqlite"
    }
    ```
- POST `/api/validate_license`
  - Body (JSON): `{ "license_key": "XXXX", "device_id": "DEVICE_SIGNATURE", "user_agent": "UA" }`
  - Response: license status (ACTIVE/PENDING/BLOCKED), category and binding info.
- POST `/api/check_device_sync`
  - Used to automatically match device hardware signature to an existing license.
- POST `/predict`
  - Body: JSON payload expected by the signal engine (e.g. market, timeframe, other params)
  - Response: signal object (direction, confidence, signal_id, timestamps)
  - Example curl:
    ```bash
    curl -X POST http://localhost:5000/predict \
      -H "Content-Type: application/json" \
      -d '{"market":"EUR/USD","asset_type":"OTC"}'
    ```
- GET `/api/win_rate`
  - Returns aggregated win rate statistics computed from `win_rate_tracking`.
- POST `/api/track_outcome`
  - Body: `{ "signal_id": "...", "outcome":"WIN" }` — records outcome for a signal.
- POST `/api/track_activity`
  - Body: telemetry data (mouse movements, clicks, current_url, etc.) — silent collection.

Note: Exact request/response shapes are defined in `app.py`. Review handlers in `app.py` for any additional request fields or required headers.

---

## Frontend usage & license unlocking flow

1. Run the backend: `python app.py` (default port 5000).
2. Open `index.html` (via static file or hosted server) — UI shows a license gate.
3. Enter license key in the AUTHORIZATION KEY input and click `UNLOCK`.
4. Frontend will call backend endpoints to validate the license and, if successful, unlock the UI.
5. Master keys (for emergency or admin testing):
   - `QXMASTER` (OWNER)
   - `ADMIN2026` (OWNER)
   - `TESTKEY01` (USER)
   - `TRIAL2026` (TRIAL)
   These are inserted by `emergency_fix.py` when executed (used in emergency scenarios).

---

## Diagnostics & Troubleshooting

Common diagnostic scripts:
- `verify_all.py` — integration checks (frontend asset checks, backend protection test, signal generation)
- `check_status.py` — checks WebSocket adapters and deterministic signal logic
- `final_diagnostic.py` — full system verification (.env, DB, license subsystem)
- `check_db_keys.py` — confirm DB contains expected keys

Troubleshooting checklist:
1. Confirm Python dependencies installed.
2. Verify `.env` exists and `DATABASE_URL` is set correctly for Postgres, or blank for SQLite.
3. Start backend and check `/test` endpoint: `curl http://localhost:5000/test`
4. If DB errors occur, run `python final_diagnostic.py` to gather info.
5. If no licenses exist or keys missing, run `python setup_licenses.py` or `python emergency_fix.py`.
6. For WebSocket broker errors referenced in `check_status.py`, ensure adapter credentials and connectivity (these are implementation-specific).

If you see messages like "[WARN] Enhanced Engine module missing", the app will continue using fallback engine — ensure optional engine module is installed or available under `engine/`.

---

## Emergency repair & master keys

If the license DB is corrupt or missing, `emergency_fix.py` can:
- Inspect existing licenses
- Insert a set of guaranteed master keys:
  - `QXMASTER`, `ADMIN2026`, `TESTKEY01`, `TRIAL2026`
- Recreate tables if needed

Use only with caution and in secure/admin contexts.

Example:
```bash
python emergency_fix.py
```

---

## Security & Deployment Notes

- Do not expose the backend `/` JSON endpoints to the public internet without appropriate authentication and HTTPS.
- Do not commit `.env` or SECRET_KEY into the repository.
- For production deployment consider:
  - Running behind HTTPS (nginx/letsencrypt)
  - Using Gunicorn / uWSGI with multiple workers
  - Using managed Postgres (Supabase, RDS) and restricting inbound DB connections
  - Logging/monitoring for suspicious license activity
- Telemetry: `track_activity` silently collects user interactions. Make sure this complies with privacy policies / laws for your users/region.

---

## Contribution & Development

- To add features or fix bugs:
  1. Create a branch: `git checkout -b feat/your-feature`
  2. Implement code and tests
  3. Open PR with clear description and examples
- Tests: Add unit tests as needed for signal engines and API handlers. There is no test harness currently; adding a pytest suite is recommended.

---

## NOTES & TODOs (observations from repo scan)

- The main backend is contained in a single file (`app.py`) and includes many responsibilities (routing, DB init, engines). Consider splitting into modules:
  - `api/` for endpoints
  - `db/` for DB helpers
  - `engines/` for signal engines
  - `admin/` for license management utilities
- Consider adding `requirements.txt` (if not present) and `Procfile` / deployment docs.
- Add unit/integration tests and CI workflow to ensure stable changes.
- If you plan to distribute, add a clear EULA and privacy policy for telemetry.

---

## License

Add your chosen license (MIT, Apache-2.0, etc.). If you want, I can add a LICENSE file for you.

---

If you'd like, I can:
- commit this README into the repository,
- split `app.py` into modules (propose a refactor),
- generate a `requirements.txt` based on imports found,
- or create example `.env.sample` file and a small systemd/gunicorn deployment example.

Tell me which of those next steps you'd like me to perform and I will proceed.
