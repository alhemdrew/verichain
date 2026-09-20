# VeriChain on Windows

This guide runs the functional VeriChain web application locally on Windows 10 or 11. It does not claim a Tauri desktop installer: `apps/desktop` is currently a scaffold and Windows packaging has not been tested in this repository.

## Prerequisites

Install:

- Python 3.11 or newer from [python.org](https://www.python.org/downloads/windows/). Enable **Add Python to PATH**.
- Node.js 18 or newer from [nodejs.org](https://nodejs.org/). npm is included.
- Git for Windows.
- A modern browser such as Chrome, Edge, or Firefox.

PostgreSQL is optional for the simplest evaluation path. The local SQLite path is suitable for a judge walkthrough. Use PostgreSQL when testing a multi-user deployment or Docker workflow.

## Install

Open PowerShell:

```powershell
git clone https://github.com/alhemdrew/verichain.git
cd verichain

py -3 -m venv apps\api\.venv
.\apps\api\.venv\Scripts\python.exe -m pip install --upgrade pip
.\apps\api\.venv\Scripts\python.exe -m pip install -r apps\api\requirements.txt

Copy-Item .env.example apps\api\.env
```

Edit `apps\api\.env` and set a private local secret:

```dotenv
ENV=development
SECRET_KEY=replace-with-a-long-random-local-value
DATABASE_URL=sqlite:///./verichain_local.db
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=http://localhost:5173
SEED_DEMO_ACCOUNTS=false
```

Install frontend dependencies:

```powershell
cd apps\web
npm ci
```

## Run the API

Open a PowerShell window at the repository root:

```powershell
cd apps\api
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave this window running. Confirm the API is healthy in another PowerShell window:

```powershell
Invoke-WebRequest http://localhost:8000/health | Select-Object -Expand Content
```

Expected response:

```json
{"status":"ok"}
```

## Run the web application

Open a second PowerShell window:

```powershell
cd apps\web
npm run dev -- --host 127.0.0.1
```

Open <http://localhost:5173> in the browser. Register a synthetic investigator account, create a case, and upload a synthetic file. Do not use real evidence or personal information for a local demonstration.

## Judge walkthrough

1. Register with a fictional name, a reserved `example.com` email, and a local password.
2. Create a case and note its organization-scoped `CASE-XXXX` number.
3. Upload a small synthetic text file.
4. Seal the evidence and inspect the SHA-256 and manifest values.
5. Sign and verify the record.
6. Compare a deliberately modified copy and confirm `NO MATCH`.
7. Open the custody timeline and provenance view.
8. Generate both report variants.
9. Synchronize local evidence only after the API is reachable.

The original evidence bytes must remain unchanged throughout this walkthrough.

## Troubleshooting

### `python` or `py` is not recognized

Reinstall Python and enable **Add Python to PATH**, then open a new PowerShell window. Verify with `py -3 --version`.

### Port 8000 or 5173 is already in use

Find the process with `Get-NetTCPConnection -LocalPort 8000` or `Get-NetTCPConnection -LocalPort 5173`. Stop only the process you recognize, or run the API/frontend on alternate ports and update `DATABASE_URL`/`FRONTEND_URL` configuration accordingly.

### The browser reports CORS errors

Ensure the frontend URL in `CORS_ORIGINS` exactly matches the URL in the browser, including the port. Restart the API after editing `apps\api\.env`.

### Uploads or local evidence disappear

The local SQLite database and evidence storage are runtime data. Back them up deliberately; they are ignored by Git and must never be committed.

### Email sharing does not send

Email delivery requires a configured SMTP provider. Set the `SMTP_*` values in `apps\api\.env`. Without them, VeriChain reports email delivery as unavailable and does not claim success.
