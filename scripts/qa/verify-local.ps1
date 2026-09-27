param([switch]$WithRunningServices)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "venv bootstrap failed" }
}
& $venvPython -m pip install --disable-pip-version-check -q -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "dev install failed" }

Write-Host "[1/4] Python regression"
& $venvPython -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

Write-Host "[2/4] Ruff"
& $venvPython -m ruff check src tests
if ($LASTEXITCODE -ne 0) { throw "ruff failed" }

Write-Host "[3/4] Manager JavaScript syntax"
& node --check web/manager/app.js
if ($LASTEXITCODE -ne 0) { throw "app.js syntax failed" }
& node --check web/manager/i18n.js
if ($LASTEXITCODE -ne 0) { throw "i18n.js syntax failed" }

Write-Host "[4/4] Portable source scan"
$bad = Get-ChildItem src,scripts -Recurse -File | Select-String -Pattern "C:\\Users\\24734|D:\\AgentData\\10_Workspaces\\coding-tools-mcp-demo"
if ($bad) { throw "machine-specific path remains in portable source/scripts" }

if ($WithRunningServices) {
    $expectedIndex = [IO.Path]::GetFullPath((Join-Path $root "runtime\state\index.json"))
    $mcp = Invoke-RestMethod "http://127.0.0.1:8943/healthz" -TimeoutSec 5
    $ui = Invoke-RestMethod "http://127.0.0.1:8955/api/health" -TimeoutSec 5

    if (-not $mcp.ok) { throw "MCP health failed" }
    $mcpIndex = [IO.Path]::GetFullPath([string]$mcp.index_path)
    if (-not [string]::Equals($mcpIndex, $expectedIndex, [StringComparison]::OrdinalIgnoreCase)) {
        throw "MCP source identity mismatch: $mcpIndex"
    }

    if (-not $ui.ok) { throw "manager health failed" }
    if (-not $ui.mutations_allowed -or -not $ui.parity.ok) {
        throw "manager canonical truth is degraded"
    }
    $uiIndex = [IO.Path]::GetFullPath([string]$ui.registry.index_path)
    if (-not [string]::Equals($uiIndex, $expectedIndex, [StringComparison]::OrdinalIgnoreCase)) {
        throw "manager source identity mismatch: $uiIndex"
    }
}
Write-Host "PASS: Skills Manager verification complete."
