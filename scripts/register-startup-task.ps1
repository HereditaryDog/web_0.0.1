$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $projectRoot "scripts\start-server-stack.ps1"
$taskName = "web001-startup-stack"
$taskCommand = "powershell.exe -ExecutionPolicy Bypass -File `"$scriptPath`""

schtasks.exe /Delete /TN $taskName /F *> $null
schtasks.exe /Create /SC ONSTART /TN $taskName /TR $taskCommand /RU SYSTEM /F | Out-Null

Write-Output "Registered startup task: $taskName"
