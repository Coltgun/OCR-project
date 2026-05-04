# run.ps1 — Launch the Simplified Chinese OCR App (PowerShell)
#
# Usage (from project root):
#   .\run.ps1
#
# If execution policy blocks this, run once:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ENV_NAME   = "chinese-ocr"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition

function Find-EnvPython([string]$envName) {
    $candidates = @(
        "$env:USERPROFILE\miniconda3\envs\$envName\python.exe",
        "$env:USERPROFILE\Miniconda3\envs\$envName\python.exe",
        "$env:USERPROFILE\anaconda3\envs\$envName\python.exe",
        "$env:LOCALAPPDATA\miniconda3\envs\$envName\python.exe",
        "C:\miniconda3\envs\$envName\python.exe",
        "C:\ProgramData\miniconda3\envs\$envName\python.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

# Locate python inside the conda env directly — no 'conda activate' needed
$pyExe = Find-EnvPython $ENV_NAME
if (-not $pyExe) {
    Write-Host ""
    Write-Host "  [ERROR] Could not find the '$ENV_NAME' conda environment." -ForegroundColor Red
    Write-Host "  Expected: %USERPROFILE%\miniconda3\envs\$ENV_NAME\python.exe" -ForegroundColor Red
    Write-Host "  Run install.ps1 to set it up." -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "  Python: $pyExe" -ForegroundColor DarkGray

# Check main.py exists
$mainPy = Join-Path $SCRIPT_DIR "main.py"
if (-not (Test-Path $mainPy)) {
    Write-Host ""
    Write-Host "  [ERROR] main.py not found in $SCRIPT_DIR" -ForegroundColor Red
    Write-Host "  Make sure you are running this script from the project root." -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "  Starting Simplified Chinese OCR App..." -ForegroundColor Cyan
Write-Host ""

Set-Location $SCRIPT_DIR

try {
    & $pyExe main.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "  [ERROR] App exited with code $LASTEXITCODE." -ForegroundColor Red
        Write-Host "  Check the output above for details." -ForegroundColor Red
        Read-Host "Press Enter to exit"
    }
} catch {
    Write-Host ""
    Write-Host "  [ERROR] $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
