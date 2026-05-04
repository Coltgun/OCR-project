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

function Find-Conda {
    $c = Get-Command "conda" -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $candidates = @(
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\Miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe",
        "C:\miniconda3\Scripts\conda.exe",
        "C:\ProgramData\miniconda3\Scripts\conda.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

# Locate conda
$condaExe = Find-Conda
if (-not $condaExe) {
    Write-Host ""
    Write-Host "  [ERROR] conda not found." -ForegroundColor Red
    Write-Host "  Run install.ps1 first, or install Miniconda3 from:" -ForegroundColor Red
    Write-Host "    https://docs.conda.io/en/latest/miniconda.html" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "  conda: $condaExe" -ForegroundColor DarkGray

# Check the environment exists
$envList = & $condaExe env list 2>&1 | Out-String
if ($envList -notmatch "\b$ENV_NAME\b") {
    Write-Host ""
    Write-Host "  [ERROR] Conda environment '$ENV_NAME' not found." -ForegroundColor Red
    Write-Host "  Run install.ps1 to set it up." -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

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
    & $condaExe run -n $ENV_NAME python main.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "  [ERROR] App exited with code $LASTEXITCODE." -ForegroundColor Red
        Read-Host "Press Enter to exit"
    }
} catch {
    Write-Host ""
    Write-Host "  [ERROR] $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
