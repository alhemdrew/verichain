$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ApiDir = Join-Path $Root "apps\api"
$WebDir = Join-Path $Root "apps\web"
$Python = Join-Path $ApiDir ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found. Run: py -3 -m venv apps\api\.venv"
}
if (-not (Test-Path (Join-Path $WebDir "package.json"))) {
    throw "Frontend package.json not found at $WebDir"
}

Start-Process -FilePath $Python `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $ApiDir

Start-Process -FilePath "cmd.exe" `
    -ArgumentList @("/c", "npm run dev -- --host 127.0.0.1") `
    -WorkingDirectory $WebDir

Write-Host "VeriChain API: http://localhost:8000/health"
Write-Host "VeriChain web: http://localhost:5173"
Write-Host "Two new terminal windows were started. Close them to stop the services."