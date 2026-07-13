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

function Get-SecureRandomBytes {
    param([int]$Length)

    $bytes = New-Object byte[] $Length
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    return (, $bytes)
}

function ConvertTo-LowerHex {
    param([byte[]]$Bytes)

    return ([BitConverter]::ToString($Bytes).Replace('-', '').ToLowerInvariant())
}

function ConvertTo-FernetKey {
    param([byte[]]$Bytes)

    return ([Convert]::ToBase64String($Bytes).Replace('+', '-').Replace('/', '_'))
}

function Write-NewEnvironmentFile {
    param([string]$EnvironmentPath)

    $mysqlPassword = ConvertTo-LowerHex (Get-SecureRandomBytes -Length 24)
    $mysqlRootPassword = ConvertTo-LowerHex (Get-SecureRandomBytes -Length 24)
    $fernetKey = ConvertTo-FernetKey (Get-SecureRandomBytes -Length 32)
    $lines = @(
        'MYSQL_DATABASE=smart_bi',
        'MYSQL_USER=smart_bi',
        "MYSQL_PASSWORD=$mysqlPassword",
        "MYSQL_ROOT_PASSWORD=$mysqlRootPassword",
        "DATABASE_URL=mysql+pymysql://smart_bi:$mysqlPassword@mysql:3306/smart_bi",
        "APP_ENCRYPTION_KEY=$fernetKey",
        'FRONTEND_ORIGIN=http://localhost:8080',
        'QUERY_TIMEOUT_SECONDS=5',
        'AI_DEFAULT_TIMEOUT_SECONDS=30'
    )
    $temporaryPath = "$EnvironmentPath.$([Guid]::NewGuid().ToString('N')).tmp"
    $content = ($lines -join [Environment]::NewLine) + [Environment]::NewLine

    try {
        [System.IO.File]::WriteAllText($temporaryPath, $content, (New-Object System.Text.UTF8Encoding($false)))
        [System.IO.File]::Move($temporaryPath, $EnvironmentPath)
        return $true
    }
    catch {
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $EnvironmentPath) {
            return $false
        }
        throw
    }
}

function Get-EnvironmentValues {
    param([string]$EnvironmentPath)

    $values = @{}
    $lineNumber = 0
    foreach ($line in [System.IO.File]::ReadAllLines($EnvironmentPath, [System.Text.Encoding]::UTF8)) {
        $lineNumber++
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }
        if ($trimmed -notmatch '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
            throw "Existing .env contains invalid syntax at line $lineNumber. Fix the file and rerun; values are not displayed for security."
        }
        $values[$Matches[1]] = $Matches[2].Trim()
    }
    return $values
}

function Assert-ValidFernetKey {
    param([string]$Key)

    try {
        if ($Key -notmatch '^[A-Za-z0-9_-]+=*$') {
            throw 'invalid'
        }
        $bytes = [Convert]::FromBase64String($Key.Replace('-', '+').Replace('_', '/'))
        if ($bytes.Length -ne 32 -or (ConvertTo-FernetKey $bytes) -cne $Key) {
            throw 'invalid'
        }
    }
    catch {
        throw 'APP_ENCRYPTION_KEY must be a URL-safe Base64 Fernet key encoding exactly 32 bytes. Generate a new key deliberately; the existing value was not changed.'
    }
}

function Assert-EnvironmentIsValid {
    param([string]$EnvironmentPath)

    $requiredNames = @(
        'MYSQL_DATABASE',
        'MYSQL_USER',
        'MYSQL_PASSWORD',
        'MYSQL_ROOT_PASSWORD',
        'DATABASE_URL',
        'APP_ENCRYPTION_KEY',
        'FRONTEND_ORIGIN',
        'QUERY_TIMEOUT_SECONDS',
        'AI_DEFAULT_TIMEOUT_SECONDS'
    )
    $values = Get-EnvironmentValues -EnvironmentPath $EnvironmentPath
    $missing = @($requiredNames | Where-Object { -not $values.ContainsKey($_) -or [string]::IsNullOrWhiteSpace($values[$_]) })
    if ($missing.Count -gt 0) {
        throw ("Existing .env is missing required non-empty values: {0}. Add only the named values and rerun; existing secrets were not changed." -f ($missing -join ', '))
    }

    Assert-ValidFernetKey -Key $values['APP_ENCRYPTION_KEY']
    foreach ($timeoutName in @('QUERY_TIMEOUT_SECONDS', 'AI_DEFAULT_TIMEOUT_SECONDS')) {
        $timeout = 0
        if (-not [int]::TryParse($values[$timeoutName], [ref]$timeout) -or $timeout -lt 1) {
            throw "$timeoutName must be a positive integer. Existing secrets were not changed."
        }
    }
}

function Wait-ForHealthyApplication {
    $deadline = (Get-Date).AddSeconds(180)
    do {
        try {
            $health = Invoke-RestMethod -Uri 'http://localhost:8080/api/health' -Method Get -TimeoutSec 5
            if ($health.data.app -eq 'up' -and $health.data.database -eq 'up' -and $health.data.seeded_orders -eq 540) {
                return
            }
        }
        catch {
            # The services may still be building, migrating, or seeding.
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    throw 'Application did not become healthy within 180 seconds. Expected app=up, database=up, and seeded_orders=540. Run docker compose ps and docker compose logs backend.'
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repositoryRoot

$docker = Get-DockerExecutable
Assert-DockerReady -Docker $docker

$environmentPath = Join-Path $repositoryRoot '.env'
if (-not (Test-Path -LiteralPath $environmentPath)) {
    $created = Write-NewEnvironmentFile -EnvironmentPath $environmentPath
    if ($created) {
        Write-Host 'Created a new local .env with generated database credentials and encryption key.'
    }
}
Assert-EnvironmentIsValid -EnvironmentPath $environmentPath

Invoke-DockerCompose -Docker $docker -Arguments @('up', '-d', '--build')
Wait-ForHealthyApplication

Write-Host 'Application: http://localhost:8080'
Write-Host 'API docs:    http://localhost:8080/api/docs'
