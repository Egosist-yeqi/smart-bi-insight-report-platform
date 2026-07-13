[CmdletBinding()]
param()

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

function Invoke-DockerCompose {
    param(
        [string]$Docker,
        [string[]]$Arguments
    )

    & $Docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose command failed. Review Docker Desktop status and run docker compose ps for service details.'
    }
}

function Wait-ForMySqlHealth {
    param([string]$Docker)

    $deadline = (Get-Date).AddSeconds(180)
    do {
        $containerId = (& $Docker compose ps -q mysql).Trim()
        if ($LASTEXITCODE -eq 0 -and $containerId) {
            $status = (& $Docker inspect --format '{{.State.Health.Status}}' $containerId).Trim()
            if ($LASTEXITCODE -eq 0 -and $status -eq 'healthy') {
                return
            }
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    throw 'MySQL did not become healthy within 180 seconds. Run docker compose ps and docker compose logs mysql.'
}

function Invoke-NpmCommand {
    param([string[]]$Arguments)

    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($null -eq $npm) {
        throw 'npm.cmd was not found. Install Node.js LTS, reopen PowerShell, then rerun this command.'
    }
    & $npm.Source @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw 'Frontend command failed. Review the command output above.'
    }
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repositoryRoot

$docker = Get-DockerExecutable
Assert-DockerReady -Docker $docker
$testServicesStarted = $false

try {
    Invoke-DockerCompose -Docker $docker -Arguments @('--profile', 'test', 'up', '-d', 'mysql', 'mock-llm')
    $testServicesStarted = $true
    Wait-ForMySqlHealth -Docker $docker

    Invoke-DockerCompose -Docker $docker -Arguments @('run', '--rm', '--no-deps', '--entrypoint', 'alembic', 'backend', 'upgrade', 'head')
    Invoke-DockerCompose -Docker $docker -Arguments @('run', '--rm', '--no-deps', '--entrypoint', 'python', 'backend', '-m', 'pytest')
    Invoke-NpmCommand -Arguments @('test')
    Invoke-NpmCommand -Arguments @('run', 'build')
}
finally {
    if ($testServicesStarted) {
        try {
            & $docker compose --profile test rm -f -s mock-llm *> $null
            if ($LASTEXITCODE -ne 0) {
                Write-Warning 'The test-only mock-llm container could not be removed automatically. No data volumes were deleted.'
            }
        }
        catch {
            Write-Warning 'The test-only mock-llm cleanup encountered an error. No data volumes were deleted.'
        }
    }
}
