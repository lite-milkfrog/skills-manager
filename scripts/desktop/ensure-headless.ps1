param([int]$TimeoutSeconds = 20)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ServerScript = Join-Path $Root "scripts\desktop\headless-server.cmd"
$BaseState = if ($env:SKILLS_MANAGER_RUNTIME_HOME) { $env:SKILLS_MANAGER_RUNTIME_HOME } else { Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) "SkillsManager" }
$StateRoot = Join-Path $BaseState "headless"
$HealthUrl = "http://127.0.0.1:8943/healthz"
$Port = 8943

function Test-Ready {
    try {
        $response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2
        return $null -ne $response
    }
    catch { return $false }
}

if (Test-Ready) { exit 0 }
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Error "Port 8943 is occupied but Skills Manager health is not ready."
    exit 3
}
New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
$stdout = Join-Path $StateRoot "headless.stdout.log"
$stderr = Join-Path $StateRoot "headless.stderr.log"
$process = Start-Process -FilePath "$env:SystemRoot\System32\cmd.exe" -ArgumentList @("/d", "/c", ('"' + $ServerScript + '"')) -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$deadline = (Get-Date).AddSeconds([Math]::Max(1, $TimeoutSeconds))
do {
    Start-Sleep -Milliseconds 250
    if (Test-Ready) {
        $owner = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        $pidValue = if ($owner) { $owner.OwningProcess } else { $process.Id }
        Set-Content -Path (Join-Path $StateRoot "headless.pid") -Value $pidValue -Encoding ascii
        exit 0
    }
    if ($process.HasExited) {
        Write-Error "Skills Manager MCP exited before readiness. See $stderr"
        exit 4
    }
} while ((Get-Date) -lt $deadline)
Write-Error "Skills Manager MCP did not become ready within $TimeoutSeconds seconds. See $stderr"
exit 5
