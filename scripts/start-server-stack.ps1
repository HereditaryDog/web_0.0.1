$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$dockerAvailable = $false
try {
    docker --version | Out-Null
    $dockerAvailable = $true
} catch {
    $dockerAvailable = $false
}

if ($dockerAvailable) {
    if (-not (Test-Path ".env.server")) {
        Copy-Item ".env.server.example" ".env.server"
        Write-Output "Created .env.server from .env.server.example. Please edit secrets before production-like use."
    }

    $composeArgs = @("compose", "--env-file", ".env.server", "up", "-d", "--build")
    if ((Get-Content ".env.server") -match "^CLOUDFLARE_TUNNEL_TOKEN=.+") {
        $composeArgs = @("compose", "--env-file", ".env.server", "--profile", "public", "up", "-d", "--build")
    }

    docker @composeArgs
    & "$projectRoot\scripts\start-quick-tunnel.ps1"
} else {
    & "$projectRoot\scripts\install-web-service.ps1"
    & "$projectRoot\scripts\start-quick-tunnel.ps1" -OriginUrl "http://127.0.0.1:8000"
}
