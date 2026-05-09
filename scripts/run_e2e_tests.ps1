param(
    [string]$BaseUrl = "http://localhost:8000/api/v1",
    [int]$Timeout = 60,
    [switch]$WaitForServer
)

$ErrorActionPreference = "Continue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$healthUrl = if ($BaseUrl -match "/v1/?$") {
    $BaseUrl -replace "/v1/?$", "/health"
} else {
    "{0}/health" -f $BaseUrl.TrimEnd("/")
}

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

$pythonCommand = Resolve-PythonCommand

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ERP E2E Test Runner" -ForegroundColor Cyan
Write-Host "  Base URL: $BaseUrl" -ForegroundColor Cyan
Write-Host "  Health URL: $healthUrl" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($WaitForServer) {
    Write-Host "Waiting for server to be ready..." -ForegroundColor Yellow
    $maxAttempts = $Timeout
    $attempt = 0
    while ($attempt -lt $maxAttempts) {
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 5 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Host "Server is ready!" -ForegroundColor Green
                break
            }
        }
        catch {}
        $attempt++
        Write-Host "  Attempt $attempt/$maxAttempts - Server not ready yet..." -ForegroundColor DarkGray
        Start-Sleep -Seconds 2
    }
    if ($attempt -ge $maxAttempts) {
        Write-Host "Server did not become ready within $Timeout seconds. Aborting." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Running E2E tests..." -ForegroundColor Yellow
& $pythonCommand.Command @($pythonCommand.Args) (Join-Path $projectDir "tests\e2e\test_e2e_core_chain.py") $BaseUrl

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "E2E tests PASSED!" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "E2E tests FAILED!" -ForegroundColor Red
}

exit $LASTEXITCODE
