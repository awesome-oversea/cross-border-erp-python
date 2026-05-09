param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,

    [string]$DB_HOST = "",
    [string]$DB_PORT = "",
    [string]$DB_USER = "",
    [string]$DB_PASS = "",
    [string]$MaintenanceDb = "postgres"
)

$ErrorActionPreference = "Stop"

if (-not $DB_HOST) {
    $DB_HOST = if ($env:DB_HOST) { $env:DB_HOST } else { "localhost" }
}

if (-not $DB_PORT) {
    $DB_PORT = if ($env:DB_PORT) { $env:DB_PORT } else { "5432" }
}

if (-not $DB_USER) {
    $DB_USER = if ($env:DB_USER) { $env:DB_USER } else { "erp" }
}

if (-not $DB_PASS) {
    $DB_PASS = $env:DB_PASSWORD
}

if (-not (Test-Path $BackupFile)) {
    Write-Error "Backup file not found: $BackupFile"
    exit 1
}

if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
    throw "psql not found. Install PostgreSQL client tools first."
}

if (-not (Get-Command gzip -ErrorAction SilentlyContinue)) {
    throw "gzip not found in PATH."
}

Write-Host "WARNING: This will restore the database from backup: $BackupFile"
Write-Host "Target: ${DB_HOST}:${DB_PORT}"
$confirm = Read-Host "Type 'CONFIRM' to proceed"
if ($confirm -ne "CONFIRM") {
    Write-Host "Restore cancelled."
    exit 0
}

$env:PGPASSWORD = $DB_PASS

try {
    Write-Host "Decompressing and restoring database..."
    gzip -dc $BackupFile | & psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $MaintenanceDb
    Write-Host "Database restore completed successfully."
} catch {
    Write-Error "Restore failed: $_"
    exit 1
} finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}
