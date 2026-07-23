[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

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

if (Test-ApplicationHealthy) {
    Write-Host 'The application is already running. Opening it in your browser...'
    Start-Process 'http://localhost:8080'
    exit 0
}

$docker = Get-DockerExecutable
Start-DockerDesktopIfNeeded -Docker $docker

& (Join-Path $PSScriptRoot 'start.ps1')
if ($LASTEXITCODE -ne 0) {
    throw 'The application startup script did not finish successfully.'
}

Start-Process 'http://localhost:8080'
