$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$runtimeDir = Join-Path $projectDir "runtime"

$DB_HOST = if ($env:DB_HOST) { $env:DB_HOST } else { "localhost" }
$DB_PORT = if ($env:DB_PORT) { $env:DB_PORT } else { "5432" }
$DB_USER = if ($env:DB_USER) { $env:DB_USER } else { "erp" }
$DB_NAME = if ($env:DB_NAME) { $env:DB_NAME } else { "erp" }
$DB_PASS = $env:DB_PASSWORD
$BACKUP_DIR = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { Join-Path $runtimeDir "backups" }
$DATE = Get-Date -Format "yyyyMMdd_HHmmss"
$BACKUP_FILE = Join-Path $BACKUP_DIR "erp_backup_$DATE.sql.gz"

if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) {
    throw "pg_dump not found. Install PostgreSQL client tools first."
}

if (-not (Get-Command gzip -ErrorAction SilentlyContinue)) {
    throw "gzip not found in PATH."
}

if (-not (Test-Path $BACKUP_DIR)) {
    New-Item -ItemType Directory -Path $BACKUP_DIR -Force | Out-Null
}

Write-Host "Starting database backup at $DATE"
Write-Host "Backup file: $BACKUP_FILE"

$env:PGPASSWORD = $DB_PASS

$dumpArgs = @(
    "-h", $DB_HOST,
    "-p", $DB_PORT,
    "-U", $DB_USER,
    "-d", $DB_NAME,
    "--clean",
    "--if-exists",
    "--create",
    "--format=plain"
)

try {
    & pg_dump @dumpArgs | gzip > $BACKUP_FILE
    $fileSize = (Get-Item $BACKUP_FILE).Length / 1MB
    Write-Host "Backup completed successfully. Size: $([math]::Round($fileSize, 2)) MB"

    $retentionDays = if ($env:RETENTION_DAYS) { [int]$env:RETENTION_DAYS } else { 30 }
    $cutoffDate = (Get-Date).AddDays(-$retentionDays)
    Get-ChildItem -Path $BACKUP_DIR -Filter "erp_backup_*.sql.gz" |
        Where-Object { $_.LastWriteTime -lt $cutoffDate } |
        ForEach-Object {
            Write-Host "Removing old backup: $($_.Name)"
            Remove-Item $_.FullName -Force
        }
} catch {
    Write-Error "Backup failed: $_"
    exit 1
} finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}
