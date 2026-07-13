$ErrorActionPreference = 'Stop'

$script:NormalComposeProjectName = 'smart-bi-insight-report-platform'
$script:TestComposeProjectName = 'smart-bi-insight-report-platform-test'

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

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Docker info *> $null
        $dockerExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($dockerExitCode -ne 0) {
        throw 'Docker Desktop is not ready. Start Docker Desktop, wait for its engine to start, then run this command again.'
    }
}

function New-ComposeContext {
    param(
        [string]$ProjectName,
        [string]$ComposeFileName
    )

    if ($ProjectName -notmatch '^[a-z0-9][a-z0-9_-]*$') {
        throw 'The fixed Docker Compose project name is invalid.'
    }

    $repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
    $composeFile = Join-Path $repositoryRoot $ComposeFileName
    if (-not (Test-Path -LiteralPath $composeFile -PathType Leaf)) {
        throw "Expected Compose file was not found in the resolved repository root: $ComposeFileName."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $repositoryRoot '.git'))) {
        throw 'Resolved repository root does not contain Git metadata; refusing to operate on Docker resources.'
    }

    return [pscustomobject]@{
        RepositoryRoot = $repositoryRoot
        ComposeFile = (Resolve-Path -LiteralPath $composeFile).Path
        ProjectName = $ProjectName
    }
}

function Invoke-PinnedCompose {
    param(
        [string]$Docker,
        [pscustomobject]$Context,
        [string[]]$Arguments
    )

    # Explicit flags override inherited COMPOSE_FILE and COMPOSE_PROJECT_NAME values.
    & $Docker compose --project-directory $Context.RepositoryRoot --project-name $Context.ProjectName --file $Context.ComposeFile @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose command failed. Review Docker Desktop status and run the documented diagnostics.'
    }
}

function Get-PinnedComposeOutput {
    param(
        [string]$Docker,
        [pscustomobject]$Context,
        [string[]]$Arguments
    )

    $output = @(& $Docker compose --project-directory $Context.RepositoryRoot --project-name $Context.ProjectName --file $Context.ComposeFile @Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose command failed. Review Docker Desktop status and run the documented diagnostics.'
    }
    return $output
}

function Assert-NormalProjectVolumeContract {
    param(
        [string]$Docker,
        [pscustomobject]$Context
    )

    $declaredVolumes = @(Get-PinnedComposeOutput -Docker $Docker -Context $Context -Arguments @('config', '--volumes') | Where-Object { $_ })
    if ($declaredVolumes.Count -ne 1 -or $declaredVolumes[0].Trim() -ne 'mysql_data') {
        throw 'Refusing reset because the normal Compose file does not declare exactly the expected mysql_data volume.'
    }

    return "$($Context.ProjectName)_mysql_data"
}

function Assert-ExpectedProjectVolume {
    param(
        [string]$Docker,
        [string]$VolumeName,
        [pscustomobject]$Context
    )

    $volumeNames = @(& $Docker volume ls --filter "name=^$([regex]::Escape($VolumeName))$" --quiet 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker could not verify the fixed normal-project volume. Refusing to continue reset.'
    }
    $existingVolume = $volumeNames | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace([string]$existingVolume)) {
        return $false
    }

    $labelOutput = @(& $Docker volume inspect --format '{{json .Labels}}' $VolumeName 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker could not inspect the fixed normal-project volume labels. Refusing to continue reset.'
    }
    $labelsJson = $labelOutput | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace([string]$labelsJson)) {
        throw 'Refusing reset because the expected Docker volume labels could not be verified.'
    }

    try {
        $labels = $labelsJson | ConvertFrom-Json
    }
    catch {
        throw 'Refusing reset because the expected Docker volume labels could not be verified.'
    }
    if ($labels.'com.docker.compose.project' -ne $Context.ProjectName -or $labels.'com.docker.compose.volume' -ne 'mysql_data') {
        throw "Refusing reset because the target Docker volume is not this fixed project's mysql_data volume."
    }
    return $true
}
