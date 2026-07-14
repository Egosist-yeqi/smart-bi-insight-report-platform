[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

function Wait-ForMySqlHealth {
    param(
        [string]$Docker,
        [pscustomobject]$Context
    )

    $deadline = (Get-Date).AddSeconds(180)
    do {
        $containerIds = @(Get-PinnedComposeOutput -Docker $Docker -Context $Context -Arguments @('ps', '-q', 'mysql'))
        $containerId = $containerIds | Select-Object -First 1
        if ($containerId) {
            $status = (& $Docker inspect --format '{{.State.Health.Status}}' $containerId.Trim()).Trim()
            if ($LASTEXITCODE -eq 0 -and $status -eq 'healthy') {
                return
            }
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    throw 'Isolated test MySQL did not become healthy within 180 seconds.'
}

function Wait-ForBackendHealth {
    param(
        [string]$Docker,
        [pscustomobject]$Context
    )

    $deadline = (Get-Date).AddSeconds(180)
    do {
        $containerIds = @(Get-PinnedComposeOutput -Docker $Docker -Context $Context -Arguments @('ps', '-q', 'backend'))
        $containerId = $containerIds | Select-Object -First 1
        if ($containerId) {
            $status = (& $Docker inspect --format '{{.State.Health.Status}}' $containerId.Trim()).Trim()
            if ($LASTEXITCODE -eq 0 -and $status -eq 'healthy') {
                return
            }
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    throw 'Isolated test backend did not reach its Docker healthcheck within 180 seconds.'
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

function Ensure-FrontendDependencies {
    $vite = Join-Path (Join-Path $context.RepositoryRoot 'node_modules') '.bin\vite.cmd'
    if (-not (Test-Path -LiteralPath (Join-Path $context.RepositoryRoot 'node_modules')) -or -not (Test-Path -LiteralPath $vite)) {
        if (-not (Test-Path -LiteralPath (Join-Path $context.RepositoryRoot 'package-lock.json'))) {
            throw 'package-lock.json is required before npm.cmd ci can prepare frontend tooling.'
        }
        Invoke-NpmCommand -Arguments @('ci')
    }
}

$context = New-ComposeContext -ProjectName $script:TestComposeProjectName -ComposeFileName 'compose.test.yaml'
Set-Location -LiteralPath $context.RepositoryRoot

$docker = Get-DockerExecutable
$primaryFailure = $null
$cleanupFailure = $null
$cleanupRequired = $false

try {
    Assert-DockerReady -Docker $docker
    $cleanupRequired = $true
    Invoke-PinnedCompose -Docker $docker -Context $context -Arguments @('up', '-d', '--build', 'mysql', 'mock-llm')
    Wait-ForMySqlHealth -Docker $docker -Context $context

    # MySQL can report a local healthcheck before it accepts network clients. The backend entrypoint
    # owns the bounded migration retry, so wait for that application-level readiness before direct checks.
    Invoke-PinnedCompose -Docker $docker -Context $context -Arguments @('up', '-d', '--build', 'backend')
    Wait-ForBackendHealth -Docker $docker -Context $context
    Invoke-PinnedCompose -Docker $docker -Context $context -Arguments @('run', '--rm', '--no-deps', '--entrypoint', 'alembic', 'backend', 'upgrade', 'head')
    Invoke-PinnedCompose -Docker $docker -Context $context -Arguments @('run', '--rm', '--no-deps', '--entrypoint', 'python', 'backend', '-m', 'pytest')

    # Integration tests intentionally write fixture rows. Recreate only the disposable test project
    # so browser acceptance always starts with the deterministic 540-order dataset.
    Invoke-PinnedCompose -Docker $docker -Context $context -Arguments @('down', '--volumes', '--remove-orphans')
    Invoke-PinnedCompose -Docker $docker -Context $context -Arguments @('up', '-d', '--build', 'mysql', 'mock-llm')
    Wait-ForMySqlHealth -Docker $docker -Context $context
    Invoke-PinnedCompose -Docker $docker -Context $context -Arguments @('up', '-d', '--build', 'backend')
    Wait-ForBackendHealth -Docker $docker -Context $context

    Ensure-FrontendDependencies
    Invoke-NpmCommand -Arguments @('test')
    Invoke-NpmCommand -Arguments @('run', 'build')
    Invoke-NpmCommand -Arguments @('run', 'test:e2e')
}
catch {
    $primaryFailure = $_
}
finally {
    if ($cleanupRequired) {
        try {
            Invoke-PinnedCompose -Docker $docker -Context $context -Arguments @('down', '--volumes', '--remove-orphans')
        }
        catch {
            $cleanupFailure = $_
        }
    }
}

if ($primaryFailure -and $cleanupFailure) {
    throw ("Test workflow failed: {0}`nIsolated test-project cleanup also failed: {1}" -f $primaryFailure.Exception.Message, $cleanupFailure.Exception.Message)
}
if ($primaryFailure) {
    throw $primaryFailure
}
if ($cleanupFailure) {
    throw ("Isolated test-project cleanup failed: {0}" -f $cleanupFailure.Exception.Message)
}
