$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $projectRoot "logs"
$logFile = Join-Path $logDir "health-check.log"
$envServer = Join-Path $projectRoot ".env.server"
$serviceName = "web001-app"
$docker = "docker"
$publicUrlFile = Join-Path $logDir "public-url.txt"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "[$timestamp] $Message"
}

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Default = ""
    )
    if (-not (Test-Path $Path)) {
        return $Default
    }
    $escapedKey = [regex]::Escape($Key)
    foreach ($line in Get-Content $Path) {
        if ($line -match "^$escapedKey=(.*)$") {
            return $Matches[1].Trim()
        }
    }
    return $Default
}

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 20
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
    } catch {
        return $false
    }
}

function Ensure-AppService {
    try {
        $service = Get-Service -Name $serviceName -ErrorAction Stop
    } catch {
        Write-Log "App service $serviceName not found."
        return $false
    }

    if ($service.Status -ne "Running") {
        Write-Log "App service not running. Restarting $serviceName."
        Restart-Service -Name $serviceName -ErrorAction Stop
        Start-Sleep -Seconds 8
    }
    return $true
}

function Ensure-DockerStack {
    try {
        & $docker --version | Out-Null
    } catch {
        Write-Log "Docker CLI not available."
        return $false
    }

    $webState = (& $docker inspect --format "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}nohealth{{end}}" web001-web 2>$null)
    $dbState = (& $docker inspect --format "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}nohealth{{end}}" web001-db 2>$null)

    if (-not $webState -or -not $dbState -or $webState -notlike "running|healthy" -or $dbState -notlike "running|healthy") {
        Write-Log "Docker stack unhealthy or missing. Recreating web stack."
        & $docker compose --env-file .env.server up -d --build | Out-Null
        Start-Sleep -Seconds 12
    }

    return $true
}

function Ensure-QuickTunnel {
    $token = Get-EnvValue -Path $envServer -Key "CLOUDFLARE_TUNNEL_TOKEN"
    if ($token) {
        Write-Log "Named Cloudflare Tunnel token detected; skipping quick tunnel monitor."
        return $null
    }

    try {
        $publicUrl = & "$projectRoot\scripts\start-quick-tunnel.ps1" -OriginUrl "http://127.0.0.1:$script:dockerAppPort"
        $publicUrl = ($publicUrl | Select-Object -Last 1).Trim()
        if ($publicUrl) {
            Write-Log "Quick tunnel available at $publicUrl"
            return $publicUrl
        }
    } catch {
        Write-Log "Failed to ensure quick tunnel: $($_.Exception.Message)"
    }

    if (Test-Path $publicUrlFile) {
        return (Get-Content $publicUrlFile -Raw).Trim()
    }

    return $null
}

$script:dockerAppPort = Get-EnvValue -Path $envServer -Key "APP_PORT" -Default "8001"
$servicePort = "8000"

Write-Log "Starting health check."

$serviceOk = Ensure-AppService
$dockerOk = Ensure-DockerStack

$serviceHealthUrl = "http://127.0.0.1:$servicePort/health/readiness/"
$dockerHealthUrl = "http://127.0.0.1:$script:dockerAppPort/health/readiness/"

if ($serviceOk -and -not (Test-HttpOk -Url $serviceHealthUrl)) {
    Write-Log "Service health endpoint failed; restarting $serviceName."
    Restart-Service -Name $serviceName -ErrorAction Stop
    Start-Sleep -Seconds 8
}

if ($dockerOk -and -not (Test-HttpOk -Url $dockerHealthUrl)) {
    Write-Log "Docker health endpoint failed; recreating web container."
    & $docker compose --env-file .env.server up -d --build web | Out-Null
    Start-Sleep -Seconds 12
}

$publicUrl = Ensure-QuickTunnel
if ($publicUrl) {
    $publicHealthUrl = "$publicUrl/health/readiness/"
    if (-not (Test-HttpOk -Url $publicHealthUrl)) {
        Write-Log "Public tunnel health endpoint failed; restarting quick tunnel."
        try {
            $publicUrl = & "$projectRoot\scripts\start-quick-tunnel.ps1" -OriginUrl "http://127.0.0.1:$script:dockerAppPort" -ForceRestart
            $publicUrl = ($publicUrl | Select-Object -Last 1).Trim()
            Write-Log "Quick tunnel restarted at $publicUrl"
        } catch {
            Write-Log "Quick tunnel restart failed: $($_.Exception.Message)"
        }
    }
}

$serviceHealthy = Test-HttpOk -Url $serviceHealthUrl
$dockerHealthy = Test-HttpOk -Url $dockerHealthUrl
$publicHealthy = $true
if ($publicUrl) {
    $publicHealthy = Test-HttpOk -Url "$publicUrl/health/readiness/"
}

if ($serviceHealthy -and $dockerHealthy -and $publicHealthy) {
    Write-Log "Health check passed."
    exit 0
}

Write-Log "Health check completed with warnings. service=$serviceHealthy docker=$dockerHealthy public=$publicHealthy"
exit 1
