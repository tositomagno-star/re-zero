param(
    [Parameter(Mandatory = $true)][string]$DatabaseUrl,
    [Parameter(Mandatory = $true)][string]$BackupFile
)

$ErrorActionPreference = "Stop"
$uri = [Uri]$DatabaseUrl
$database = $uri.AbsolutePath.TrimStart("/")
$hashFile = "$BackupFile.sha256"
if (Test-Path $hashFile) {
    $expected = (Get-Content $hashFile -Raw).Split(" ")[0]
    $actual = (Get-FileHash $BackupFile -Algorithm SHA256).Hash.ToLower()
    if ($expected -ne $actual) { throw "Integridade do backup inválida." }
}
& pg_restore --clean --if-exists --dbname=$database $BackupFile
if ($LASTEXITCODE -ne 0) { throw "pg_restore falhou." }
