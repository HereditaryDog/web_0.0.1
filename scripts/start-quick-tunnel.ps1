param(
    [string]$OriginUrl = "http://127.0.0.1:8001",
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $projectRoot "logs"
$stderrLog = Join-Path $logDir "cloudflared-quick.err.log"
$stdoutLog = Join-Path $logDir "cloudflared-quick.log"
$urlFile = Join-Path $logDir "public-url.txt"
$workspaceUserHome = Split-Path (Split-Path $projectRoot -Parent) -Parent
$envServer = Join-Path $projectRoot ".env.server"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$cloudflaredCandidates = @(
    "$env:LOCALAPPDATA\Microsoft\WinGet\Links\cloudflared.exe",
    (Join-Path $workspaceUserHome "AppData\Local\Microsoft\WinGet\Links\cloudflared.exe")
)

try {
    $cloudflaredCommand = Get-Command cloudflared.exe -ErrorAction Stop
    $cloudflaredCandidates += $cloudflaredCommand.Source
} catch {
}

$cloudflared = $cloudflaredCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not (Test-Path $cloudflared)) {
    throw "cloudflared.exe not found."
}

if ((Test-Path $envServer) -and ((Get-Content $envServer) -match "^CLOUDFLARE_TUNNEL_TOKEN=.+")) {
    Write-Output "Named Cloudflare Tunnel token detected; quick tunnel not started."
    exit 0
}

$quickTunnelProcesses = @(Get-CimInstance Win32_Process -Filter "Name = 'cloudflared.exe'" | Where-Object {
    $_.CommandLine -like "*tunnel*" -and $_.CommandLine -like "*--url $OriginUrl*"
})

if ($ForceRestart -and $quickTunnelProcesses) {
    foreach ($proc in $quickTunnelProcesses) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    $quickTunnelProcesses = @()
}

if (-not $quickTunnelProcesses) {
    Remove-Item $stdoutLog, $stderrLog -ErrorAction SilentlyContinue
    Start-Process `
        -FilePath $cloudflared `
        -ArgumentList @("tunnel", "--url", $OriginUrl, "--no-autoupdate") `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -WindowStyle Hidden | Out-Null
}

$publicUrl = $null
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if (Test-Path $stderrLog) {
        $content = Get-Content $stderrLog -Raw -ErrorAction SilentlyContinue
        $match = [regex]::Match($content, "https://[a-z0-9-]+\.trycloudflare\.com")
        if ($match.Success) {
            $publicUrl = $match.Value
            break
        }
    }
    Start-Sleep -Seconds 1
}

if (-not $publicUrl) {
    throw "Quick tunnel started but no public URL was found in log output."
}

Set-Content -Path $urlFile -Value $publicUrl
Write-Output $publicUrl
