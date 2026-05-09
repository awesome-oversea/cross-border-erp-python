$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$runtimeDir = Join-Path $projectDir "runtime"
$banditReport = Join-Path $runtimeDir "bandit-report.json"

function Resolve-PythonCommand {
    $venvCandidates = @(
        (Join-Path $projectDir "venv\Scripts\python.exe"),
        (Join-Path $projectDir ".venv\Scripts\python.exe"),
        (Join-Path $projectDir "env\venv\Scripts\python.exe")
    )

    foreach ($candidate in $venvCandidates) {
        if (Test-Path $candidate) {
            return @{
                Command = $candidate
                Args = @()
            }
        }
    }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.11 --version *> $null
        if ($LASTEXITCODE -eq 0) {
            return @{
                Command = "py"
                Args = @("-3.11")
            }
        }

        & py --version *> $null
        if ($LASTEXITCODE -eq 0) {
            return @{
                Command = "py"
                Args = @()
            }
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{
            Command = "python"
            Args = @()
        }
    }

    throw "Python runtime not found. Install Python 3.11+ or create a repository-local venv."
}

function Invoke-Python {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    & $script:pythonCommand.Command @($script:pythonCommand.Args) @Args
}

if (-not (Test-Path $runtimeDir)) {
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
}

$pythonCommand = Resolve-PythonCommand

Write-Host "=== ERP Python Security Scan ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Running Bandit (SAST)..." -ForegroundColor Yellow
$banditResult = Invoke-Python -m bandit -r (Join-Path $projectDir "src\erp") -f json -o $banditReport 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Bandit: No issues found" -ForegroundColor Green
} else {
    Write-Host "  Bandit: Issues found - see $banditReport" -ForegroundColor Red
}

Write-Host ""
Write-Host "[2/3] Running pip-audit (Dependency Vulnerability Scan)..." -ForegroundColor Yellow
$auditResult = Invoke-Python -m pip_audit --desc --progress-spinner off 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  pip-audit: No known vulnerabilities" -ForegroundColor Green
} else {
    Write-Host "  pip-audit: Vulnerabilities found" -ForegroundColor Red
    Write-Host $auditResult
}

Write-Host ""
Write-Host "[3/3] Checking for insecure dependencies..." -ForegroundColor Yellow
$insecurePackages = @("pickle", "yaml.unsafe_load", "eval", "exec")
$foundIssues = $false
Get-ChildItem -Path (Join-Path $projectDir "src\erp") -Filter "*.py" -Recurse | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    foreach ($pattern in $insecurePackages) {
        if ($content -match $pattern) {
            Write-Host "  Warning: Found '$pattern' in $($_.Name)" -ForegroundColor Yellow
            $foundIssues = $true
        }
    }
}

if (-not $foundIssues) {
    Write-Host "  No insecure patterns detected" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Security Scan Complete ===" -ForegroundColor Cyan
