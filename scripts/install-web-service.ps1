$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$serviceName = "web001-app"
$nssm = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\nssm.exe"
$powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$scriptPath = Join-Path $projectRoot "scripts\run-web-server.ps1"
$logDir = Join-Path $projectRoot "logs"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $nssm)) {
    throw "nssm.exe not found. Please install NSSM first."
}

& $nssm install $serviceName $powershell "-ExecutionPolicy Bypass -File `"$scriptPath`""
& $nssm set $serviceName AppDirectory $projectRoot
& $nssm set $serviceName DisplayName "G-MasterToken App Service"
& $nssm set $serviceName Description "Runs G-MasterToken via Waitress on 127.0.0.1:8000"
& $nssm set $serviceName Start SERVICE_AUTO_START
& $nssm set $serviceName AppStdout (Join-Path $logDir "app-service.out.log")
& $nssm set $serviceName AppStderr (Join-Path $logDir "app-service.err.log")
& $nssm set $serviceName AppRotateFiles 1
& $nssm set $serviceName AppRotateOnline 1
& $nssm set $serviceName AppRotateBytes 10485760
& $nssm set $serviceName AppExit Default Restart
& $nssm start $serviceName

Write-Output "Installed and started service: $serviceName"
