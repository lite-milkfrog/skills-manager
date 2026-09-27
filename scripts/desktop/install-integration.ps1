$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Ensure = Join-Path $Root "scripts\desktop\ensure-manager.ps1"
$EnsureHeadless = Join-Path $Root "scripts\desktop\ensure-headless.ps1"
$Open = Join-Path $Root "scripts\desktop\open-manager.ps1"
$Icon = Join-Path $Root "web\manager\assets\skill-control-plane.ico"
$LocalAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
$Desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)
$WacLocal = Join-Path $LocalAppData "WebGPT-as-Codex"
$EnsureDir = Join-Path $WacLocal "external-ensure"
$ComponentDir = Join-Path $WacLocal "config\components"
$EnsureWrapper = Join-Path $EnsureDir "skills-control-plane.ps1"
$ComponentPath = Join-Path $ComponentDir "skills-control-plane.json"
$LegacyShortcut = Join-Path $Desktop "Skill Control Plane.lnk"
$FrontendShortcut = Join-Path $Desktop "Skills Manager.url"
$Begin = "REM Skill Control Plane integration BEGIN"
$End = "REM Skill Control Plane integration END"

foreach ($required in @($EnsureHeadless, $Ensure, $Open, $Icon)) {
    if (-not (Test-Path $required)) { throw "Required integration file is missing: $required" }
}
New-Item -ItemType Directory -Path $EnsureDir -Force | Out-Null
New-Item -ItemType Directory -Path $ComponentDir -Force | Out-Null

$wrapper = @'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "__HEADLESS__"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "__MANAGER__"
exit $LASTEXITCODE
'@
$wrapper = $wrapper.Replace("__HEADLESS__", $EnsureHeadless).Replace("__MANAGER__", $Ensure)
[IO.File]::WriteAllText($EnsureWrapper, $wrapper, [Text.UTF8Encoding]::new($false))

$component = [ordered]@{
    id = "skills-control-plane"
    display_name = "Skills Manager"
    role = "canonical_skill_workflow_backend"
    required = $true
    enabled_by_default = $true
    transport = "streamable_http"
    default_endpoint = "http://127.0.0.1:8943/mcp"
    safe_tool = $null
    ownership_mode = "external_local"
    startup_priority = 25
    dependencies = @("mcpjungle")
    readiness_contract = "mcp-initialize-tools-list"
    gateway_exposure = "gateway"
    refresh_registration = $true
    process_contains = @("skill_control_plane", "8943")
}
[IO.File]::WriteAllText(
    $ComponentPath,
    (($component | ConvertTo-Json -Depth 5) + [Environment]::NewLine),
    [Text.UTF8Encoding]::new($false)
)

# Older SCP generations inserted a prestart block. Remove only that owned block.
$Prestart = Join-Path $WacLocal "local-prestart.cmd"
if (Test-Path $Prestart) {
    $text = Get-Content $Prestart -Raw
    $pattern = "(?ms)^" + [Regex]::Escape($Begin) + ".*?^" + [Regex]::Escape($End) + "\r?\n?"
    if ($text -match [Regex]::Escape($Begin)) {
        $text = [Regex]::Replace($text, $pattern, "")
        [IO.File]::WriteAllText($Prestart, $text, [Text.UTF8Encoding]::new($false))
    }
}

# Retire only the old SCP-owned runtime-starting Desktop shortcut.
# Keep a frontend-only Internet shortcut; lifecycle startup still belongs to WAC.
$urlShortcut = @"
[InternetShortcut]
URL=http://127.0.0.1:8955/
IconFile=$Icon
IconIndex=0
"@
[IO.File]::WriteAllText($FrontendShortcut, $urlShortcut, [Text.UTF8Encoding]::new($false))

$shortcutState = "absent"
if (Test-Path $LegacyShortcut) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($LegacyShortcut)
    if ($shortcut.TargetPath -match "powershell\.exe$" -and $shortcut.Arguments -eq ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $Open + '"')) {
        Remove-Item $LegacyShortcut -Force
        $shortcutState = "retired-owned"
    }
    else {
        $shortcutState = "preserved-unmanaged"
    }
}

[pscustomobject]@{
    ok = $true
    canonical_mcp = "http://127.0.0.1:8943/mcp"
    ensure_wrapper = $EnsureWrapper
    component_overlay = $ComponentPath
    legacy_shortcut = $shortcutState
    frontend_shortcut = $FrontendShortcut
    frontend_shortcut_mode = "open-only"
    integration = "WAC RuntimeSupervisor owns discovery/ensure; SCP provides canonical backend"
} | ConvertTo-Json -Depth 4
