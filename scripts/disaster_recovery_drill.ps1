param(
    [string]$DB_HOST = "localhost",
    [string]$DB_PORT = "5432",
    [string]$DB_USER = "erp",
    [string]$DB_NAME = "erp",
    [string]$DB_PASS = "",
    [string]$BACKUP_DIR = "",
    [string]$REPORT_FILE = "",
    [string]$SOURCE_BACKUP_DIR = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$runtimeDir = Join-Path $projectDir "runtime"

if (-not $DB_PASS) {
    if ($env:DB_PASSWORD) {
        $DB_PASS = $env:DB_PASSWORD
    } else {
        $DB_PASS = $env:PGPASSWORD
    }
}

if (-not $BACKUP_DIR) {
    $BACKUP_DIR = Join-Path $runtimeDir "disaster-recovery"
}

if (-not $REPORT_FILE) {
    $REPORT_FILE = Join-Path $runtimeDir "dr-drill-report.txt"
}

if (-not $SOURCE_BACKUP_DIR) {
    $SOURCE_BACKUP_DIR = Join-Path $runtimeDir "backups"
}

foreach ($tool in @("psql", "gzip")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool not found. Install PostgreSQL client tools and gzip first."
    }
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$drillDir = Join-Path $BACKUP_DIR "drill_$timestamp"
New-Item -ItemType Directory -Path $drillDir -Force | Out-Null

$reportLines = New-Object System.Collections.Generic.List[string]

function Add-ReportLine {
    param([string]$Line)

    $script:reportLines.Add($Line) | Out-Null
}

Write-Host "=== Disaster Recovery Drill Start ===" -ForegroundColor Cyan
Write-Host "Timestamp: $timestamp" -ForegroundColor Yellow
Write-Host "Drill directory: $drillDir" -ForegroundColor Yellow

Add-ReportLine "Disaster Recovery Drill Report"
Add-ReportLine "=============================="
Add-ReportLine "Timestamp: $timestamp"
Add-ReportLine "Project root: $projectDir"
Add-ReportLine ""

Write-Host "[1/6] Locating latest backup..." -ForegroundColor Yellow
$latestBackup = Get-ChildItem -Path $SOURCE_BACKUP_DIR -Filter "erp_backup_*.sql.gz" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $latestBackup) {
    Write-Host "  No backup file found in $SOURCE_BACKUP_DIR" -ForegroundColor Red
    Add-ReportLine "[FAIL] No backup file found in $SOURCE_BACKUP_DIR"
    $reportLines | Out-File -FilePath $REPORT_FILE -Encoding UTF8
    exit 1
}

$backupAge = (Get-Date) - $latestBackup.LastWriteTime
$rpoMinutes = [math]::Floor($backupAge.TotalMinutes)
Write-Host "  Latest backup: $($latestBackup.Name) (age: ${rpoMinutes}m)" -ForegroundColor Green
Add-ReportLine "[PASS] Latest backup found: $($latestBackup.Name)"
Add-ReportLine "  RPO: ${rpoMinutes} minutes"

Write-Host "[2/6] Validating backup size..." -ForegroundColor Yellow
$backupSizeMb = [math]::Round($latestBackup.Length / 1MB, 2)
if ($latestBackup.Length -gt 1KB) {
    Write-Host "  Backup size: ${backupSizeMb} MB" -ForegroundColor Green
    Add-ReportLine "[PASS] Backup size looks valid: ${backupSizeMb} MB"
} else {
    Write-Host "  Backup file is unexpectedly small" -ForegroundColor Red
    Add-ReportLine "[FAIL] Backup file is unexpectedly small: $($latestBackup.Length) bytes"
}

Write-Host "[3/6] Rehearsing restore to an isolated drill database..." -ForegroundColor Yellow
$restoreDbBase = ("{0}_dr_{1}" -f $DB_NAME, $timestamp).ToLower() -replace "[^a-z0-9_]", "_"
$restoreDb = if ($restoreDbBase.Length -gt 63) { $restoreDbBase.Substring(0, 63) } else { $restoreDbBase }
$decompressedFile = Join-Path $drillDir "restore.sql"
$rewrittenFile = Join-Path $drillDir "restore_drill.sql"
$restoreStart = Get-Date
$rtoSeconds = -1
$restoreSucceeded = $false

try {
    $env:PGPASSWORD = $DB_PASS
    & psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c "DROP DATABASE IF EXISTS $restoreDb WITH (FORCE);" 2>&1 | Out-Null
    & gzip -dc $latestBackup.FullName > $decompressedFile 2>&1

    $backupSql = Get-Content $decompressedFile -Raw
    $backupSql = $backupSql.Replace("CREATE DATABASE $DB_NAME", "CREATE DATABASE $restoreDb")
    $backupSql = $backupSql.Replace("\connect $DB_NAME", "\connect $restoreDb")
    Set-Content -Path $rewrittenFile -Value $backupSql -Encoding UTF8

    & psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -f $rewrittenFile 2>&1 | Out-Null

    $restoreEnd = Get-Date
    $rtoSeconds = [math]::Floor(($restoreEnd - $restoreStart).TotalSeconds)
    $restoreSucceeded = $true
    Write-Host "  Restore completed. RTO: ${rtoSeconds}s" -ForegroundColor Green
    Add-ReportLine "[PASS] Restore rehearsal succeeded"
    Add-ReportLine "  RTO: ${rtoSeconds} seconds"
} catch {
    Write-Host "  Restore rehearsal failed: $_" -ForegroundColor Red
    Add-ReportLine "[FAIL] Restore rehearsal failed: $_"
} finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Host "[4/6] Verifying restored database contents..." -ForegroundColor Yellow
if ($restoreSucceeded) {
    try {
        $env:PGPASSWORD = $DB_PASS
        $tableCountRaw = & psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $restoreDb -t -A -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema');" 2>&1
        $tableCount = [int]($tableCountRaw | Select-Object -Last 1).Trim()
        Write-Host "  Restored table count: $tableCount" -ForegroundColor Green
        Add-ReportLine "[INFO] Restored table count: $tableCount"
    } catch {
        Write-Host "  Failed to inspect restored database: $_" -ForegroundColor Red
        Add-ReportLine "[WARN] Failed to inspect restored database: $_"
    } finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }
} else {
    Add-ReportLine "[WARN] Restore verification skipped because the restore rehearsal failed"
}

Write-Host "[5/6] Cleaning up drill database..." -ForegroundColor Yellow
try {
    $env:PGPASSWORD = $DB_PASS
    & psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c "DROP DATABASE IF EXISTS $restoreDb WITH (FORCE);" 2>&1 | Out-Null
    Write-Host "  Cleanup completed" -ForegroundColor Green
    Add-ReportLine "[PASS] Drill database cleanup completed"
} catch {
    Write-Host "  Cleanup failed: $_" -ForegroundColor Red
    Add-ReportLine "[WARN] Drill database cleanup failed: $_"
} finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Host "[6/6] Writing drill report..." -ForegroundColor Yellow
Add-ReportLine ""
Add-ReportLine "Conclusion"
Add-ReportLine "----------"
Add-ReportLine "Target RPO: 60 minutes"
Add-ReportLine "Target RTO: 1800 seconds"
Add-ReportLine "Actual RPO: $(if ($latestBackup) { "${rpoMinutes} minutes" } else { "N/A" })"
Add-ReportLine "Actual RTO: $(if ($rtoSeconds -ge 0) { "${rtoSeconds} seconds" } else { "N/A" })"
Add-ReportLine "RPO within target: $(if ($rpoMinutes -le 60) { "yes" } else { "no" })"
Add-ReportLine "RTO within target: $(if ($rtoSeconds -ge 0 -and $rtoSeconds -le 1800) { "yes" } else { "no" })"

$reportLines | Out-File -FilePath $REPORT_FILE -Encoding UTF8
Write-Host "Report written to $REPORT_FILE" -ForegroundColor Green
Write-Host "=== Disaster Recovery Drill Complete ===" -ForegroundColor Cyan
