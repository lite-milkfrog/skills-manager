$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Ensure = Join-Path $Root "scripts\desktop\ensure-manager.ps1"
& powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File $Ensure
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Start-Process "http://127.0.0.1:8955/"
exit 0
