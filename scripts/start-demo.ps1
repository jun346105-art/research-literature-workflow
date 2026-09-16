[CmdletBinding()]
param([int]$Port = 8015)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project virtual environment not found: .venv\Scripts\python.exe"
}

$listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host "LitFlow Demo is already listening at http://127.0.0.1:$Port/ (PID $($listener.OwningProcess))."
    Start-Process "http://127.0.0.1:$Port/"
    exit 0
}

Set-Location $repoRoot
$env:PYTHONPATH = Join-Path $repoRoot 'src'
Write-Host "Starting LitFlow Research Copilot Demo at http://127.0.0.1:$Port/"
Write-Host "Offline mode: no API key and no external Provider calls. Press Ctrl+C to stop."
& $python -m uvicorn litflow_api.app:app --host 127.0.0.1 --port $Port --log-level info
exit $LASTEXITCODE
