[CmdletBinding()]
param(
    [switch]$ConfirmReset
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

if (-not $ConfirmReset) {
    throw 'Refusing to delete MySQL data. Re-run with -ConfirmReset.'
}

$context = New-ComposeContext -ProjectName $script:NormalComposeProjectName -ComposeFileName 'compose.yaml'
Set-Location -LiteralPath $context.RepositoryRoot

$docker = Get-DockerExecutable
Assert-DockerReady -Docker $docker
$volumeName = Assert-NormalProjectVolumeContract -Docker $docker -Context $context
Invoke-PinnedCompose -Docker $docker -Context $context -Arguments @('down')

if (Assert-ExpectedProjectVolume -Docker $docker -VolumeName $volumeName -Context $context) {
    & $docker volume rm $volumeName
    if ($LASTEXITCODE -ne 0) {
        throw 'The fixed normal-project MySQL data volume could not be removed.'
    }
}

& (Join-Path $PSScriptRoot 'start.ps1')
