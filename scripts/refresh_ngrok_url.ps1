param(
    [string]$BackendEnvPath = "backend/.env"
)

$ErrorActionPreference = "Stop"

function Get-ActiveNgrokUrl {
    try {
        $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 5
    } catch {
        return $null
    }

    $httpsTunnel = $tunnels.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1
    if ($httpsTunnel -and $httpsTunnel.public_url) {
        return $httpsTunnel.public_url.TrimEnd("/")
    }
    return $null
}

function Wait-ForNgrok {
    param([int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $url = Get-ActiveNgrokUrl
        if ($url) { return $url }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    throw "Unable to detect an active ngrok HTTPS tunnel."
}

function Test-PublicHealth {
    param([string]$BaseUrl)
    $deadline = (Get-Date).AddSeconds(30)
    do {
        try {
            $resp = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/health" -TimeoutSec 10
            if ($resp.StatusCode -eq 200) { return $true }
        } catch {
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    throw "Public /health did not return 200 for $BaseUrl."
}

function Update-EnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value
    )

    $lines = @()
    if (Test-Path $Path) {
        $lines = Get-Content $Path
    }
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$([regex]::Escape($Key))=") {
            $lines[$i] = "$Key=$Value"
            $found = $true
            break
        }
    }
    if (-not $found) {
        $lines += "$Key=$Value"
    }
    Set-Content -Path $Path -Value $lines
}

$ngrokUrl = Wait-ForNgrok
Write-Host "Active ngrok URL: $ngrokUrl"
Test-PublicHealth -BaseUrl $ngrokUrl

Update-EnvValue -Path $BackendEnvPath -Key "PUBLIC_BACKEND_URL" -Value $ngrokUrl
Write-Host "Updated $BackendEnvPath"

docker compose up --build -d backend | Out-Host
docker compose exec backend alembic upgrade head | Out-Host

$backendUrl = docker compose exec backend python -c "from app.config import settings; print(settings.public_backend_url)" | Out-String
Write-Host "Backend loaded PUBLIC_BACKEND_URL: $($backendUrl.Trim())"

Test-PublicHealth -BaseUrl $ngrokUrl

try {
    $twiml = Invoke-WebRequest -UseBasicParsing -Uri "$ngrokUrl/voice/reminders/33/twiml" -TimeoutSec 10
    Write-Host "Reminder TwiML status: $($twiml.StatusCode)"
    Write-Host "Reminder TwiML content-type: $($twiml.Headers.'Content-Type')"
} catch {
    Write-Host "Reminder TwiML check failed: $($_.Exception.Message)"
    throw
}

Write-Host "ngrok refresh complete"
