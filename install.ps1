# install.ps1 — Automated installer for the Simplified Chinese OCR App
# Run from the project root:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned   (once, if needed)
#   .\install.ps1
#
# What this script does:
#   1. Checks NVIDIA driver / CUDA version
#   2. Auto-installs Miniconda3 if conda is not found
#   3. Creates the 'chinese-ocr' conda environment (Python 3.11)
#   4. Installs conda-forge packages (numpy, pillow, opencv)
#   5. Installs PySide6
#   6. Installs PaddlePaddle GPU (official PaddlePaddle index)
#   7. Installs PaddleOCR + paddlex[ocr]
#   8. Installs PyTorch (CUDA 12.1 wheel)
#   9. Installs remaining pip dependencies
#  10. Optionally installs Ollama (prompts user)
#  11. Copies config.example.json -> config.json if config.json is missing
#  12. Runs scripts/verify_env.py and prints PASS/FAIL summary

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ENV_NAME    = "chinese-ocr"
$PYTHON_VER  = "3.11"
$SCRIPT_DIR  = Split-Path -Parent $MyInvocation.MyCommand.Definition

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Header([string]$text) {
    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ("=" * 72) -ForegroundColor Cyan
}

function Write-Step([string]$text) {
    Write-Host ""
    Write-Host ">> $text" -ForegroundColor Yellow
}

function Write-OK([string]$text) {
    Write-Host "  [OK]  $text" -ForegroundColor Green
}

function Write-Warn([string]$text) {
    Write-Host "  [WARN] $text" -ForegroundColor Yellow
}

function Write-Fail([string]$text) {
    Write-Host "  [FAIL] $text" -ForegroundColor Red
}

function Find-Conda {
    # Search PATH first
    $c = Get-Command "conda" -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    # Common default locations
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

function Invoke-Conda([string]$condaExe, [string]$args) {
    $result = & $condaExe $args.Split(" ") 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "conda command failed (exit $LASTEXITCODE): conda $args"
    }
    return $result
}

function Invoke-CondaPip([string]$condaExe, [string]$pipArgs) {
    # Run pip inside the target env via: conda run -n ENV pip ...
    $allArgs = @("run", "-n", $ENV_NAME, "pip") + $pipArgs.Split(" ")
    $result = & $condaExe @allArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "pip command failed (exit $LASTEXITCODE): pip $pipArgs"
    }
    return $result
}

# ---------------------------------------------------------------------------
# Step 1 — CUDA check
# ---------------------------------------------------------------------------

Write-Header "Step 1/12 — CUDA / NVIDIA Driver Check"

try {
    $smi = & nvidia-smi 2>&1 | Out-String
    if ($smi -match "CUDA Version:\s*([\d.]+)") {
        $cudaVer = $Matches[1]
        if ($cudaVer -match "^12\.") {
            Write-OK "CUDA $cudaVer detected — compatible with PaddlePaddle GPU."
        } elseif ($cudaVer -match "^13\.") {
            Write-Warn "CUDA $cudaVer detected. PaddlePaddle GPU requires CUDA <=12.9."
            Write-Warn "Download CUDA 12.6 Toolkit: https://developer.nvidia.com/cuda-12-6-0-download-archive"
            Write-Host ""
            $cont = Read-Host "Continue anyway? (y/N)"
            if ($cont -notmatch "^[Yy]") {
                Write-Host "Aborted. Install CUDA 12.x, then re-run this script." -ForegroundColor Red
                exit 1
            }
        } else {
            Write-Warn "CUDA $cudaVer detected. Proceeding — verify compatibility manually."
        }
    } else {
        Write-Warn "Could not parse CUDA version from nvidia-smi output."
    }
} catch {
    Write-Warn "nvidia-smi not found. Ensure your NVIDIA driver is installed."
    Write-Warn "Driver download: https://www.nvidia.com/Download/index.aspx"
    $cont = Read-Host "Continue anyway? (y/N)"
    if ($cont -notmatch "^[Yy]") { exit 1 }
}

# ---------------------------------------------------------------------------
# Step 2 — Miniconda
# ---------------------------------------------------------------------------

Write-Header "Step 2/12 — Miniconda3"

$condaExe = Find-Conda

if ($condaExe) {
    Write-OK "conda found: $condaExe"
} else {
    Write-Step "conda not found — downloading Miniconda3..."
    $minicondaUrl = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
    $minicondaInstaller = "$env:TEMP\Miniconda3-latest-Windows-x86_64.exe"
    $minicondaTarget = "$env:USERPROFILE\miniconda3"

    Write-Host "  Downloading from $minicondaUrl ..."
    Invoke-WebRequest -Uri $minicondaUrl -OutFile $minicondaInstaller -UseBasicParsing

    Write-Host "  Installing Miniconda3 to $minicondaTarget (silent)..."
    $proc = Start-Process -FilePath $minicondaInstaller `
        -ArgumentList "/S /D=$minicondaTarget" `
        -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -ne 0) {
        Write-Fail "Miniconda installer exited with code $($proc.ExitCode)."
        exit 1
    }

    # Refresh PATH so conda is visible in this session
    $env:PATH = "$minicondaTarget\Scripts;$minicondaTarget\condabin;" + $env:PATH
    $condaExe = "$minicondaTarget\Scripts\conda.exe"

    if (-not (Test-Path $condaExe)) {
        Write-Fail "Miniconda installed but conda.exe not found at expected path."
        Write-Fail "Open a new terminal, re-activate the environment, and re-run install.ps1."
        exit 1
    }
    Write-OK "Miniconda3 installed: $condaExe"

    # Init conda for the current shell (needed for 'conda activate' to work)
    & $condaExe init powershell 2>&1 | Out-Null
}

# ---------------------------------------------------------------------------
# Step 3 — Create conda environment
# ---------------------------------------------------------------------------

Write-Header "Step 3/12 — Conda Environment '$ENV_NAME'"

$envList = & $condaExe env list 2>&1 | Out-String
if ($envList -match "\b$ENV_NAME\b") {
    Write-OK "Environment '$ENV_NAME' already exists — skipping creation."
} else {
    Write-Step "Creating conda environment '$ENV_NAME' with Python $PYTHON_VER..."
    & $condaExe create -n $ENV_NAME python=$PYTHON_VER -y 2>&1 | Write-Host
    if ($LASTEXITCODE -ne 0) { throw "Failed to create conda environment." }
    Write-OK "Environment '$ENV_NAME' created."
}

Write-Host ""
Write-Host "  NOTE: opencv is installed as headless (no Qt6 GUI) to avoid a Qt DLL" -ForegroundColor DarkGray
Write-Host "  conflict with pip PySide6. PySide6 is pinned to 6.8.3 which bundles" -ForegroundColor DarkGray
Write-Host "  its own ICU DLLs — required on Windows without a system CUDA Qt." -ForegroundColor DarkGray

# ---------------------------------------------------------------------------
# Step 4 — conda-forge packages
# ---------------------------------------------------------------------------

Write-Header "Step 4/12 — conda-forge: numpy, pillow, opencv (headless)"
Write-Step "Installing numpy, pillow via conda-forge..."
& $condaExe install -n $ENV_NAME -c conda-forge "numpy>=2.0,<2.3" pillow -y 2>&1 | Write-Host
if ($LASTEXITCODE -ne 0) { throw "Failed to install numpy/pillow." }
Write-Step "Installing opencv headless (no Qt6 GUI build) via conda-forge..."
& $condaExe install -n $ENV_NAME -c conda-forge "opencv=4.13.0=headless_py311hda24cb1_1" -y 2>&1 | Write-Host
if ($LASTEXITCODE -ne 0) { throw "Failed to install opencv headless." }
Write-OK "conda-forge packages installed."

# ---------------------------------------------------------------------------
# Step 5 — PySide6
# ---------------------------------------------------------------------------

Write-Header "Step 5/12 — PySide6 6.8.3"
Write-Step "Installing PySide6==6.8.3 (bundles its own ICU DLLs — required on Windows)..."
Invoke-CondaPip $condaExe "install PySide6==6.8.3" | Write-Host
Write-OK "PySide6 6.8.3 installed."

# ---------------------------------------------------------------------------
# Step 6 — PaddlePaddle GPU
# ---------------------------------------------------------------------------

Write-Header "Step 6/12 — PaddlePaddle GPU (official index)"
Write-Step "Installing paddlepaddle-gpu==3.0.0 from PaddlePaddle official index..."
Write-Host "  NOTE: Using plain pip — not uv. Do not interrupt this step." -ForegroundColor Yellow
$paddleArgs = @("run", "-n", $ENV_NAME, "pip", "install",
    "paddlepaddle-gpu==3.0.0",
    "-i", "https://www.paddlepaddle.org.cn/packages/stable/cu126/")
& $condaExe @paddleArgs 2>&1 | Write-Host
if ($LASTEXITCODE -ne 0) { throw "PaddlePaddle GPU installation failed." }
Write-OK "PaddlePaddle GPU installed."

# ---------------------------------------------------------------------------
# Step 7 — PaddleOCR
# ---------------------------------------------------------------------------

Write-Header "Step 7/12 — PaddleOCR + paddlex[ocr]"
Write-Step "Installing paddleocr..."
Invoke-CondaPip $condaExe "install paddleocr" | Write-Host
Write-Step "Installing paddlex[ocr]..."
$paddlexArgs = @("run", "-n", $ENV_NAME, "pip", "install", "paddlex[ocr]")
& $condaExe @paddlexArgs 2>&1 | Write-Host
if ($LASTEXITCODE -ne 0) { throw "paddlex[ocr] installation failed." }
Write-OK "PaddleOCR + paddlex installed."

# ---------------------------------------------------------------------------
# Step 8 — PyTorch
# ---------------------------------------------------------------------------

Write-Header "Step 8/12 — PyTorch (CUDA 12.1 wheel)"
Write-Step "Installing torch + torchvision from PyTorch official CUDA 12.1 index..."
$torchArgs = @("run", "-n", $ENV_NAME, "pip", "install",
    "torch", "torchvision",
    "--index-url", "https://download.pytorch.org/whl/cu121")
& $condaExe @torchArgs 2>&1 | Write-Host
if ($LASTEXITCODE -ne 0) { throw "PyTorch installation failed." }
Write-OK "PyTorch installed."

# ---------------------------------------------------------------------------
# Step 9 — Remaining pip dependencies
# ---------------------------------------------------------------------------

Write-Header "Step 9/12 — Remaining pip dependencies"
Write-Step "Installing mss, ebooklib, pycorrector, datasketch, sentence-transformers, etc..."
$remainingPkgs = "mss ebooklib pycorrector datasketch sentence-transformers gitpython openai pynput chardet opencc-python-reimplemented jieba"
Invoke-CondaPip $condaExe "install $remainingPkgs" | Write-Host
Write-OK "Remaining dependencies installed."

# ---------------------------------------------------------------------------
# Step 10 — Ollama (optional)
# ---------------------------------------------------------------------------

Write-Header "Step 10/12 — Ollama (optional, for LOCAL_LLM / HYBRID_TIERED modes)"

$ollamaFound = Get-Command "ollama" -ErrorAction SilentlyContinue
if ($ollamaFound) {
    Write-OK "Ollama already installed: $($ollamaFound.Source)"
} else {
    Write-Host ""
    Write-Host "  Ollama is not installed." -ForegroundColor Yellow
    Write-Host "  It is required for LOCAL_LLM and HYBRID_TIERED pipeline modes." -ForegroundColor Yellow
    Write-Host "  The app works without it (use LOCAL_FAST mode instead)." -ForegroundColor Yellow
    Write-Host ""
    $installOllama = Read-Host "  Install Ollama now? [Y/N]"
    if ($installOllama -match "^[Yy]") {
        $ollamaUrl = "https://ollama.com/download/OllamaSetup.exe"
        $ollamaInstaller = "$env:TEMP\OllamaSetup.exe"
        Write-Host "  Downloading Ollama from $ollamaUrl ..."
        Invoke-WebRequest -Uri $ollamaUrl -OutFile $ollamaInstaller -UseBasicParsing
        Write-Host "  Installing Ollama (silent)..."
        $proc = Start-Process -FilePath $ollamaInstaller -ArgumentList "/S" -Wait -PassThru -NoNewWindow
        if ($proc.ExitCode -ne 0) {
            Write-Warn "Ollama installer exited with code $($proc.ExitCode). Install manually from https://ollama.com"
        } else {
            Write-OK "Ollama installed."
            Write-Host ""
            Write-Host "  To download the default LLM model (5 GB, run after install):" -ForegroundColor Cyan
            Write-Host "    ollama pull qwen2.5:7b-instruct-q4_K_M" -ForegroundColor Cyan
        }
    } else {
        Write-OK "Ollama skipped. Set pipeline mode to LOCAL_FAST in Settings to avoid needing it."
    }
}

# ---------------------------------------------------------------------------
# Step 11 — Config file
# ---------------------------------------------------------------------------

Write-Header "Step 11/12 — config.json"

$configPath  = Join-Path $SCRIPT_DIR "config.json"
$examplePath = Join-Path $SCRIPT_DIR "config.example.json"

if (Test-Path $configPath) {
    Write-OK "config.json already exists — not overwritten."
} elseif (Test-Path $examplePath) {
    Copy-Item $examplePath $configPath
    Write-OK "config.json created from config.example.json."
    Write-Host "  Edit config.json to set:" -ForegroundColor Cyan
    Write-Host "    working_root_dir   — folder where sessions are stored" -ForegroundColor Cyan
    Write-Host "    epub_output_dir    — folder for EPUB exports" -ForegroundColor Cyan
    Write-Host "    vram_tier          — '8gb' or '16gb' (match your GPU)" -ForegroundColor Cyan
    Write-Host "    openrouter_api_key — only needed for API_STANDARD / API_FULL modes" -ForegroundColor Cyan
} else {
    Write-Warn "config.example.json not found. Copy it manually after install."
}

# ---------------------------------------------------------------------------
# Step 12 — Verify environment
# ---------------------------------------------------------------------------

Write-Header "Step 12/12 — Environment Verification"
Write-Step "Running scripts/verify_env.py..."

$verifyScript = Join-Path $SCRIPT_DIR "scripts\verify_env.py"
if (Test-Path $verifyScript) {
    $verifyArgs = @("run", "-n", $ENV_NAME, "python", $verifyScript)
    & $condaExe @verifyArgs 2>&1 | Write-Host
} else {
    Write-Warn "scripts/verify_env.py not found — skipping verification."
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

Write-Header "Installation Complete"
Write-Host ""
Write-Host "  To launch the app:" -ForegroundColor Green
Write-Host "    Double-click  run.bat            (easiest)" -ForegroundColor Green
Write-Host "    Or run:       .\run.ps1           (PowerShell)" -ForegroundColor Green
Write-Host "    Or run:       make_shortcut.bat   (create Desktop icon, then double-click)" -ForegroundColor Green
Write-Host ""
Write-Host "  If this is your first time, edit config.json before launching." -ForegroundColor Yellow
Write-Host ""
