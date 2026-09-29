<#
.SYNOPSIS
    Uploads Lunifier Windows Store MSIX packages to a Cloudflare R2 bucket.

.DESCRIPTION
    Wraps scripts/push_msix_to_r2.py to push MSIX packages to Cloudflare R2.
    Reads credentials from parameters, environment variables, or .env file.

.PARAMETER AccountId
    Cloudflare Account ID (defaults to $env:R2_ACCOUNT_ID).

.PARAMETER AccessKeyId
    Cloudflare R2 Access Key ID (defaults to $env:R2_ACCESS_KEY_ID).

.PARAMETER SecretAccessKey
    Cloudflare R2 Secret Access Key (defaults to $env:R2_SECRET_ACCESS_KEY).

.PARAMETER Bucket
    Cloudflare R2 Bucket Name (defaults to $env:R2_BUCKET_NAME).

.PARAMETER Prefix
    Destination path prefix in R2 bucket (default: 'msix/').

.PARAMETER Version
    Package version to upload ('latest', 'all', or specific e.g. '2.2.2'). Default: 'latest'.

.PARAMETER Edition
    Filter edition: 'all' (default), 'standard', or 'nobtsync'.

.PARAMETER PublicUrl
    Base public URL if R2 bucket is connected to a custom domain or r2.dev subdomain.

.PARAMETER DryRun
    Preview actions without performing any network write requests.

.EXAMPLE
    .\scripts\push_msix_to_r2.ps1 -DryRun
    .\scripts\push_msix_to_r2.ps1 -Bucket "my-r2-bucket" -AccountId "xxxx" -AccessKeyId "yyyy" -SecretAccessKey "zzzz"
#>

[CmdletBinding()]
param (
    [string]$AccountId = $env:R2_ACCOUNT_ID,
    [string]$AccessKeyId = $env:R2_ACCESS_KEY_ID,
    [string]$SecretAccessKey = $env:R2_SECRET_ACCESS_KEY,
    [string]$Bucket = $env:R2_BUCKET_NAME,
    [string]$Prefix = $(if ($env:R2_PREFIX) { $env:R2_PREFIX } else { "msix/" }),
    [string]$Version = "latest",
    [ValidateSet("all", "standard", "nobtsync")]
    [string]$Edition = "all",
    [string]$PublicUrl = $env:R2_PUBLIC_URL,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "push_msix_to_r2.py"

$argsList = @(
    $pythonScript,
    "--version", $Version,
    "--edition", $Edition,
    "--prefix", $Prefix
)

if ($AccountId) { $argsList += @("--account-id", $AccountId) }
if ($AccessKeyId) { $argsList += @("--access-key-id", $AccessKeyId) }
if ($SecretAccessKey) { $argsList += @("--secret-access-key", $SecretAccessKey) }
if ($Bucket) { $argsList += @("--bucket", $Bucket) }
if ($PublicUrl) { $argsList += @("--public-url", $PublicUrl) }
if ($DryRun) { $argsList += @("--dry-run") }

& python @argsList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
