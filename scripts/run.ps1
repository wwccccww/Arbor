# One-command local workbench (Windows PowerShell).
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/run.ps1
# Then open http://127.0.0.1:8000

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Get-Python {
    foreach ($candidate in @("python", "py")) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) { return $candidate }
    }
    throw "未找到 python。请安装 Python 3.11+ 并勾选 Add python.exe to PATH。"
}

$Python = Get-Python
$PyArgs = @()
if ($Python -eq "py") { $PyArgs = @("-3") }

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "已复制 .env.example -> .env，请填入 DEEPSEEK_API_KEY 后再开真实对话。"
}

$HasKey = $false
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^\s*DEEPSEEK_API_KEY=(.+)$') {
        $value = $Matches[1].Trim().Trim('"').Trim("'")
        if ($value) { $HasKey = $true }
    }
}
if (-not $HasKey) {
    Write-Host "未检测到 DEEPSEEK_API_KEY：对话将使用脚本回复。到 https://platform.deepseek.com 创建密钥后写入 .env。"
}

Write-Host "安装 Python 依赖..."
& $Python @PyArgs -m pip install -e ".[api,postgres]"
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Write-Host "构建工作台..."
Set-Location (Join-Path $Root "apps\web")
npm install
if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
Set-Location $Root

Write-Host "启动 http://127.0.0.1:8000 （Ctrl+C 结束）"
& $Python @PyArgs -m uvicorn apps.api.main:create_app_from_env --factory --host 127.0.0.1 --port 8000
