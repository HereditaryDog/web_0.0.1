$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $projectRoot "scripts\check-server-health.ps1"
$taskName = "web001-health-check"
$taskCommand = "powershell.exe -ExecutionPolicy Bypass -File `"$scriptPath`""

cmd.exe /c "schtasks.exe /Delete /TN $taskName /F >nul 2>&1" | Out-Null
schtasks.exe /Create /SC MINUTE /MO 30 /TN $taskName /TR $taskCommand /RU SYSTEM /F | Out-Null

Write-Output "Registered scheduled task: $taskName"
