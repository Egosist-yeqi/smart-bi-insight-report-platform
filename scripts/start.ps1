[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

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

function Get-EnvironmentDocument {
    param([string]$EnvironmentPath)

    $bytes = [System.IO.File]::ReadAllBytes($EnvironmentPath)
    $offset = 0
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $encoding = New-Object System.Text.UTF8Encoding($true, $true)
        $offset = 3
    }
    elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        $encoding = New-Object System.Text.UnicodeEncoding($false, $true, $true)
        $offset = 2
    }
    elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
        $encoding = New-Object System.Text.UnicodeEncoding($true, $true, $true)
        $offset = 2
    }
    else {
        $encoding = New-Object System.Text.UTF8Encoding($false, $true)
    }

    try {
        $text = $encoding.GetString($bytes, $offset, $bytes.Length - $offset)
    }
    catch {
        throw 'Existing .env is not valid UTF-8 or UTF-16 text. Convert it deliberately before retrying; no values were changed.'
    }
    return [pscustomobject]@{ Text = $text; Encoding = $encoding }
}

function Get-EnvironmentValues {
    param([pscustomobject]$Document)

    $values = @{}
    $lineNumber = 0
    foreach ($line in ($Document.Text -split "`r?`n")) {
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

function Write-EnvironmentTextAtomically {
    param(
        [string]$EnvironmentPath,
        [pscustomobject]$Document,
        [string]$Text
    )

    $body = $Document.Encoding.GetBytes($Text)
    $preamble = $Document.Encoding.GetPreamble()
    $bytes = New-Object byte[] ($preamble.Length + $body.Length)
    [System.Array]::Copy($preamble, 0, $bytes, 0, $preamble.Length)
    [System.Array]::Copy($body, 0, $bytes, $preamble.Length, $body.Length)
    $temporaryPath = "$EnvironmentPath.$([Guid]::NewGuid().ToString('N')).tmp"
    $backupPath = "$temporaryPath.backup"

    try {
        [System.IO.File]::WriteAllBytes($temporaryPath, $bytes)
        [System.IO.File]::Replace($temporaryPath, $EnvironmentPath, $backupPath)
    }
    catch {
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
        }
        throw 'Could not update the existing .env atomically. No replacement was made; close any editor holding the file and retry.'
    }
    if (Test-Path -LiteralPath $backupPath) {
        Remove-Item -LiteralPath $backupPath -Force
    }
}

function Write-NewEnvironmentFile {
    param([string]$EnvironmentPath)

    $mysqlPassword = ConvertTo-LowerHex (Get-SecureRandomBytes -Length 24)
    $mysqlRootPassword = ConvertTo-LowerHex (Get-SecureRandomBytes -Length 24)
    $fernetKey = ConvertTo-FernetKey (Get-SecureRandomBytes -Length 32)
    $content = @(
        'MYSQL_DATABASE=smart_bi',
        'MYSQL_USER=smart_bi',
        "MYSQL_PASSWORD=$mysqlPassword",
        "MYSQL_ROOT_PASSWORD=$mysqlRootPassword",
        "DATABASE_URL=mysql+pymysql://smart_bi:$mysqlPassword@mysql:3306/smart_bi",
        "APP_ENCRYPTION_KEY=$fernetKey",
        'FRONTEND_ORIGIN=http://localhost:8080',
        'QUERY_TIMEOUT_SECONDS=5',
        'AI_DEFAULT_TIMEOUT_SECONDS=30'
    ) -join [Environment]::NewLine
    $temporaryPath = "$EnvironmentPath.$([Guid]::NewGuid().ToString('N')).tmp"

    try {
        [System.IO.File]::WriteAllText($temporaryPath, "$content$([Environment]::NewLine)", (New-Object System.Text.UTF8Encoding($false)))
        [System.IO.File]::Move($temporaryPath, $EnvironmentPath)
    }
    catch {
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $EnvironmentPath) {
            return
        }
        throw
    }
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

function Assert-EnvironmentIsValidAndAddDefaults {
    param([string]$EnvironmentPath)

    $document = Get-EnvironmentDocument -EnvironmentPath $EnvironmentPath
    $values = Get-EnvironmentValues -Document $document
    $requiredNames = @('MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'DATABASE_URL', 'APP_ENCRYPTION_KEY', 'FRONTEND_ORIGIN')
    $missing = @($requiredNames | Where-Object { -not $values.ContainsKey($_) -or [string]::IsNullOrWhiteSpace($values[$_]) })
    if ($missing.Count -gt 0) {
        throw ("Existing .env is missing required non-empty values: {0}. Add only the named values and rerun; existing secrets were not changed." -f ($missing -join ', '))
    }
    Assert-ValidFernetKey -Key $values['APP_ENCRYPTION_KEY']

    $defaultsToAdd = @()
    foreach ($default in @(@{ Name = 'QUERY_TIMEOUT_SECONDS'; Value = '5' }, @{ Name = 'AI_DEFAULT_TIMEOUT_SECONDS'; Value = '30' })) {
        if ($values.ContainsKey($default.Name)) {
            $timeout = 0
            if (-not [int]::TryParse($values[$default.Name], [ref]$timeout) -or $timeout -lt 1) {
                throw "$($default.Name) must be a positive integer. Existing secrets were not changed."
            }
        }
        else {
            $defaultsToAdd += "$($default.Name)=$($default.Value)"
        }
    }

    if ($defaultsToAdd.Count -gt 0) {
        $newline = if ($document.Text.Contains("`r`n")) { "`r`n" } else { "`n" }
        $updatedText = $document.Text
        if ($updatedText.Length -gt 0 -and -not ($updatedText.EndsWith("`n") -or $updatedText.EndsWith("`r"))) {
            $updatedText += $newline
        }
        $updatedText += ($defaultsToAdd -join $newline) + $newline
        Write-EnvironmentTextAtomically -EnvironmentPath $EnvironmentPath -Document $document -Text $updatedText
        Write-Host 'Added missing non-secret timeout defaults to the existing .env.'
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

$context = New-ComposeContext -ProjectName $script:NormalComposeProjectName -ComposeFileName 'compose.yaml'
Set-Location -LiteralPath $context.RepositoryRoot

$docker = Get-DockerExecutable
Assert-DockerReady -Docker $docker

$environmentPath = Join-Path $context.RepositoryRoot '.env'
if (-not (Test-Path -LiteralPath $environmentPath)) {
    Write-NewEnvironmentFile -EnvironmentPath $environmentPath
    Write-Host 'Created a new local .env with generated database credentials and encryption key.'
}
Assert-EnvironmentIsValidAndAddDefaults -EnvironmentPath $environmentPath

Invoke-PinnedCompose -Docker $docker -Context $context -Arguments @('up', '-d', '--build')
Wait-ForHealthyApplication

Write-Host 'Application: http://localhost:8080'
Write-Host 'API docs:    http://localhost:8080/api/docs'
