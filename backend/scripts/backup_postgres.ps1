param(
    [Parameter(Mandatory = $true)][string]$DatabaseUrl,
    [string]$OutputDirectory = ".\backups"
)

$ErrorActionPreference = "Stop"
$uri = [Uri]$DatabaseUrl
$database = $uri.AbsolutePath.TrimStart("/")
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$output = Join-Path $OutputDirectory "$database-$timestamp.sql"
& pg_dump $database --file=$output --format=custom
if ($LASTEXITCODE -ne 0) { throw "pg_dump falhou." }
Get-FileHash $output -Algorithm SHA256 | Out-File "$output.sha256"
Write-Output $output
