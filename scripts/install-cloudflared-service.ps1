$ErrorActionPreference = "Stop"

param(
    [Parameter(Mandatory = $true)]
    [string]$TunnelToken
)

$serviceName = "web001-tunnel"
$nssm = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\nssm.exe"
$cloudflared = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\cloudflared.exe"
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $projectRoot "logs"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $nssm)) {
    throw "nssm.exe not found. Please install NSSM first."
}

if (-not (Test-Path $cloudflared)) {
    throw "cloudflared.exe not found. Please install cloudflared first."
}

& $nssm install $serviceName $cloudflared "tunnel --no-autoupdate run --token $TunnelToken"
& $nssm set $serviceName AppDirectory $projectRoot
& $nssm set $serviceName DisplayName "G-MasterToken Cloudflare Tunnel"
& $nssm set $serviceName Description "Cloudflare Tunnel for public access to G-MasterToken"
& $nssm set $serviceName Start SERVICE_AUTO_START
& $nssm set $serviceName AppStdout (Join-Path $logDir "cloudflared.out.log")
& $nssm set $serviceName AppStderr (Join-Path $logDir "cloudflared.err.log")
& $nssm set $serviceName AppRotateFiles 1
& $nssm set $serviceName AppRotateOnline 1
& $nssm set $serviceName AppRotateBytes 10485760
& $nssm set $serviceName AppExit Default Restart
& $nssm start $serviceName

Write-Output "Installed and started service: $serviceName"
