[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

$context = New-ComposeContext -ProjectName $script:NormalComposeProjectName -ComposeFileName 'compose.yaml'
Set-Location -LiteralPath $context.RepositoryRoot

$docker = Get-DockerExecutable
Assert-DockerReady -Docker $docker
Invoke-PinnedCompose -Docker $docker -Context $context -Arguments @('down')

Write-Host 'Services stopped. The fixed normal-project MySQL data volume was preserved.'
