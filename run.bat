@echo off
:: run.bat — Launch the Simplified Chinese OCR App
:: Double-click this file from the project folder.

setlocal

:: Locate conda
set "CONDA_EXE="
if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe"     set "CONDA_EXE=%USERPROFILE%\miniconda3\Scripts\conda.exe"
if exist "%USERPROFILE%\Miniconda3\Scripts\conda.exe"     set "CONDA_EXE=%USERPROFILE%\Miniconda3\Scripts\conda.exe"
if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe"      set "CONDA_EXE=%USERPROFILE%\anaconda3\Scripts\conda.exe"
if exist "%LOCALAPPDATA%\miniconda3\Scripts\conda.exe"    set "CONDA_EXE=%LOCALAPPDATA%\miniconda3\Scripts\conda.exe"
if exist "C:\miniconda3\Scripts\conda.exe"                set "CONDA_EXE=C:\miniconda3\Scripts\conda.exe"
if exist "C:\ProgramData\miniconda3\Scripts\conda.exe"    set "CONDA_EXE=C:\ProgramData\miniconda3\Scripts\conda.exe"

:: Fall back to PATH
if "%CONDA_EXE%"=="" (
    where conda >nul 2>&1
    if %errorlevel%==0 set "CONDA_EXE=conda"
)

if "%CONDA_EXE%"=="" (
    echo.
    echo  [ERROR] conda not found.
    echo  Run install.ps1 first, or install Miniconda3 from:
    echo    https://docs.conda.io/en/latest/miniconda.html
    echo.
    pause
    exit /b 1
)

:: Change to the project directory (handles launching from Desktop shortcut)
cd /d "%~dp0"

:: Activate env and run
echo  Activating chinese-ocr environment...
call "%CONDA_EXE%" run -n chinese-ocr python main.py
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] App exited with error code %errorlevel%.
    echo  If the environment is missing, run install.ps1.
    echo.
    pause
)
endlocal
