param([int]$TimeoutSeconds = 15)
$ErrorActionPreference = "Stop"
$env:SKILLS_MANAGER_USER_HOME = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ServerScript = Join-Path $Root "scripts\desktop\manager-server.cmd"
$BaseState = if ($env:SKILLS_MANAGER_RUNTIME_HOME) { $env:SKILLS_MANAGER_RUNTIME_HOME } else { Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) "SkillsManager" }
$StateRoot = Join-Path $BaseState "web-manager"
$HealthUrl = "http://127.0.0.1:8955/api/health"
$Port = 8955
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$SourceRoot = Join-Path $Root "src"
New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
$ReconcileLog = Join-Path $StateRoot "registry-reconcile.log"

function Get-Health {
    try {
        return Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2
    }
    catch { return $null }
}

function Test-Ready {
    $response = Get-Health
    return $null -ne $response -and $response.ok -eq $true
}

function Repair-RegistryParity {
    $health = Get-Health
    if ($null -eq $health -or $health.ok -eq $true) { return $health.ok -eq $true }
    if ($health.parity.ok -ne $false) { return $false }
    if ([int]$health.active_deployment_transactions -ne 0) { return $false }
    if (-not (Test-Path -LiteralPath $Python)) { return $false }

    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = $SourceRoot
        & $Python -m skill_control_plane.server state-reconcile *> $ReconcileLog
        if ($LASTEXITCODE -ne 0) { return $false }
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
    }
    return Test-Ready
}

if (Test-Ready) { exit 0 }
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    if (Repair-RegistryParity) { exit 0 }
    Write-Error "Port $Port is occupied but Skills Manager UI health is not ready. Refusing to kill or replace the owning process."
    exit 3
}
$stdout = Join-Path $StateRoot "manager.stdout.log"
$stderr = Join-Path $StateRoot "manager.stderr.log"
$process = Start-Process -FilePath "$env:SystemRoot\System32\cmd.exe" -ArgumentList @("/d", "/c", ('"' + $ServerScript + '"')) -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$deadline = (Get-Date).AddSeconds([Math]::Max(1, $TimeoutSeconds))
$repairAttempted = $false
do {
    Start-Sleep -Milliseconds 250
    if (Test-Ready) {
        Set-Content -Path (Join-Path $StateRoot "manager.pid") -Value $process.Id -Encoding ascii
        exit 0
    }
    if (-not $repairAttempted) {
        $health = Get-Health
        if (
            $null -ne $health -and
            $health.parity.ok -eq $false -and
            [int]$health.active_deployment_transactions -eq 0
        ) {
            $repairAttempted = $true
            if (Repair-RegistryParity) {
                Set-Content -Path (Join-Path $StateRoot "manager.pid") -Value $process.Id -Encoding ascii
                exit 0
            }
        }
    }
    if ($process.HasExited) {
        Write-Error "Skills Manager UI exited before readiness. See $stderr"
        exit 4
    }
} while ((Get-Date) -lt $deadline)
Write-Error "Skills Manager UI did not become ready within $TimeoutSeconds seconds. See $stderr"
exit 5
