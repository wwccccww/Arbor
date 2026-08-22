# One-command local workbench for Windows PowerShell 5+.
# Saved as UTF-8 with BOM so Chinese Windows does not break quotes.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/run.ps1
# Then open http://127.0.0.1:8000

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = $null
$PyArgs = @()
if (Get-Command python -ErrorAction SilentlyContinue) {
    $Python = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $Python = "py"
    $PyArgs = @("-3")
} else {
    throw "python not found. Install Python 3.11+ and check Add python.exe to PATH."
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Set DEEPSEEK_API_KEY for real chat."
}

$HasKey = $false
Get-Content -Path ".env" | ForEach-Object {
    if ($_ -match '^\s*DEEPSEEK_API_KEY=(.+)$') {
        $value = $Matches[1].Trim().Trim('"').Trim("'")
        if ($value) { $HasKey = $true }
    }
}
if (-not $HasKey) {
    Write-Host "DEEPSEEK_API_KEY is empty. Chat will be scripted. Get a key at https://platform.deepseek.com"
}

Write-Host "Installing Python packages..."
& $Python @PyArgs -m pip install -e ".[api,postgres]"
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Write-Host "Building web UI..."
Set-Location (Join-Path $Root "apps\web")
npm install
if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
Set-Location $Root

Write-Host "Starting http://127.0.0.1:8000  (Ctrl+C to stop)"
& $Python @PyArgs -m uvicorn apps.api.main:create_app_from_env --factory --host 127.0.0.1 --port 8000
