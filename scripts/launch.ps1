[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$logDirectory = Join-Path $repositoryRoot 'logs'
$logPath = Join-Path $logDirectory 'launcher-latest.log'
$composeLogPath = Join-Path $logDirectory 'docker-compose-latest.log'
$transcriptStarted = $false
$exitCode = 0
$previousComposeLog = $env:SMART_BI_COMPOSE_LOG

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Remove-Item -LiteralPath $composeLogPath -Force -ErrorAction SilentlyContinue
$env:SMART_BI_COMPOSE_LOG = $composeLogPath
try {
    Start-Transcript -LiteralPath $logPath -Force | Out-Null
    $transcriptStarted = $true
}
catch {
    Write-Warning "Could not create the launcher transcript at $logPath. Startup will continue."
}

function Test-ApplicationHealthy {
    try {
        $health = Invoke-RestMethod -Uri 'http://localhost:8080/api/health' -Method Get -TimeoutSec 3
        return $health.data.app -eq 'up' -and $health.data.database -eq 'up'
    }
    catch {
        return $false
    }
}

function Start-DockerDesktopIfNeeded {
    param([string]$Docker)

    try {
        Assert-DockerReady -Docker $Docker
        return
    }
    catch {
        $desktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
        if (-not (Test-Path -LiteralPath $desktop -PathType Leaf)) {
            throw 'Docker Desktop is not installed. Install it with winget install --exact --id Docker.DockerDesktop, then run this launcher again.'
        }

        Write-Host 'Docker Desktop is starting. This can take up to two minutes...'
        Start-Process -FilePath $desktop -WindowStyle Hidden
        $deadline = (Get-Date).AddSeconds(180)
        do {
            Start-Sleep -Seconds 3
            try {
                Assert-DockerReady -Docker $Docker
                return
            }
            catch {
                # Docker Desktop is still initializing its Linux engine.
            }
        } while ((Get-Date) -lt $deadline)

        throw 'Docker Desktop did not become ready within 180 seconds. Open Docker Desktop, complete any WSL prompt, then run this launcher again.'
    }
}

function Open-ApplicationBrowser {
    $applicationUrl = 'http://localhost:8080'
    Write-Host "Opening the complete Smart BI system: $applicationUrl"
    try {
        Start-Process -FilePath $applicationUrl -ErrorAction Stop
    }
    catch {
        Start-Process -FilePath 'explorer.exe' -ArgumentList $applicationUrl -ErrorAction Stop
    }
}

function Start-ApplicationWithRecovery {
    $startScript = Join-Path $PSScriptRoot 'start.ps1'
    $buildErrors = @()

    foreach ($attempt in 1..2) {
        try {
            Write-Host "Starting the full system (build attempt $attempt of 2)..."
            & $startScript
            return
        }
        catch {
            $buildErrors += $_.Exception.Message
            Write-Warning "Build attempt $attempt failed: $($_.Exception.Message)"
            if ($attempt -lt 2) {
                Write-Host 'Waiting five seconds before retrying the Docker build...'
                Start-Sleep -Seconds 5
            }
        }
    }

    Write-Warning 'Both build attempts failed. Trying the last successfully built local images so the system can still start.'
    try {
        & $startScript -UseExistingImages
    }
    catch {
        $summary = ($buildErrors | Select-Object -Unique) -join ' | '
        throw "The full system could not start after two build attempts and a local-image recovery attempt. Build errors: $summary. Recovery error: $($_.Exception.Message)"
    }
}

try {
    if (Test-ApplicationHealthy) {
        Write-Host 'The complete system is already healthy.'
    }
    else {
        $docker = Get-DockerExecutable
        Start-DockerDesktopIfNeeded -Docker $docker
        Start-ApplicationWithRecovery
    }

    if (-not (Test-ApplicationHealthy)) {
        throw 'The startup command completed, but the application health endpoint is not ready.'
    }

    Write-Host 'Smart BI is ready. MySQL, backend, and frontend passed the startup health check.'
    Open-ApplicationBrowser
}
catch {
    $exitCode = 1
    Write-Host ''
    Write-Host "Startup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Complete startup log: $logPath" -ForegroundColor Yellow
    Write-Host "Original Docker output: $composeLogPath" -ForegroundColor Yellow
}
finally {
    if ($transcriptStarted) {
        Stop-Transcript | Out-Null
    }
    $env:SMART_BI_COMPOSE_LOG = $previousComposeLog
}

exit $exitCode
