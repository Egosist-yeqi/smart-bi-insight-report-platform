[CmdletBinding()]
param(
    [switch]$ConfirmReset
)

$ErrorActionPreference = 'Stop'

function Get-DockerExecutable {
    $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    if ($null -ne $dockerCommand) {
        $candidate = if ($dockerCommand.Source) { $dockerCommand.Source } else { $dockerCommand.Path }
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    $dockerDesktopCli = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    if (Test-Path -LiteralPath $dockerDesktopCli) {
        return $dockerDesktopCli
    }

    throw 'Docker CLI was not found. Install Docker Desktop with winget install --exact --id Docker.DockerDesktop, then start Docker Desktop and try again.'
}

function Assert-DockerReady {
    param([string]$Docker)

    & $Docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Desktop is not ready. Start Docker Desktop, wait for its engine to start, then run this command again.'
    }
}

if (-not $ConfirmReset) {
    throw 'Refusing to delete MySQL data. Re-run with -ConfirmReset.'
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repositoryRoot

$docker = Get-DockerExecutable
Assert-DockerReady -Docker $docker
& $docker compose down --volumes
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose could not remove this project's MySQL volume. Run docker compose ps for details."
}

& (Join-Path $PSScriptRoot 'start.ps1')
