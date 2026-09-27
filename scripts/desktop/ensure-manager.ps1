param([int]$TimeoutSeconds = 15)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ServerScript = Join-Path $Root "scripts\desktop\manager-server.cmd"
$BaseState = if ($env:SKILLS_MANAGER_RUNTIME_HOME) { $env:SKILLS_MANAGER_RUNTIME_HOME } else { Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) "SkillsManager" }
$StateRoot = Join-Path $BaseState "web-manager"
$HealthUrl = "http://127.0.0.1:8955/api/health"
$Port = 8955

function Test-Ready {
    try {
        $response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2
        return $response.ok -eq $true
    }
    catch { return $false }
}

if (Test-Ready) { exit 0 }
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Error "Port $Port is occupied but Skills Manager UI health is not ready. Refusing to kill or replace the owning process."
    exit 3
}
New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
$stdout = Join-Path $StateRoot "manager.stdout.log"
$stderr = Join-Path $StateRoot "manager.stderr.log"
$process = Start-Process -FilePath "$env:SystemRoot\System32\cmd.exe" -ArgumentList @("/d", "/c", ('"' + $ServerScript + '"')) -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$deadline = (Get-Date).AddSeconds([Math]::Max(1, $TimeoutSeconds))
do {
    Start-Sleep -Milliseconds 250
    if (Test-Ready) {
        Set-Content -Path (Join-Path $StateRoot "manager.pid") -Value $process.Id -Encoding ascii
        exit 0
    }
    if ($process.HasExited) {
        Write-Error "Skills Manager UI exited before readiness. See $stderr"
        exit 4
    }
} while ((Get-Date) -lt $deadline)
Write-Error "Skills Manager UI did not become ready within $TimeoutSeconds seconds. See $stderr"
exit 5
