@echo off
:: run.bat — Launch the Simplified Chinese OCR App
:: Double-click this file from the project folder, or run it from a terminal.

setlocal

:: Change to the project directory (handles launching from Desktop shortcut)
cd /d "%~dp0"

:: ---------------------------------------------------------------------------
:: Find the Python executable inside the chinese-ocr conda environment.
:: We search the most common Miniconda/Anaconda install locations directly
:: rather than relying on 'conda activate', which requires shell hooks that
:: are not available in a plain cmd.exe double-click context.
:: ---------------------------------------------------------------------------
set "PY_EXE="

:: 1. Standard user-level Miniconda3
if exist "%USERPROFILE%\miniconda3\envs\chinese-ocr\python.exe" (
    set "PY_EXE=%USERPROFILE%\miniconda3\envs\chinese-ocr\python.exe"
    goto :found
)
:: 2. Capitalised variant
if exist "%USERPROFILE%\Miniconda3\envs\chinese-ocr\python.exe" (
    set "PY_EXE=%USERPROFILE%\Miniconda3\envs\chinese-ocr\python.exe"
    goto :found
)
:: 3. Anaconda3
if exist "%USERPROFILE%\anaconda3\envs\chinese-ocr\python.exe" (
    set "PY_EXE=%USERPROFILE%\anaconda3\envs\chinese-ocr\python.exe"
    goto :found
)
:: 4. LocalAppData Miniconda
if exist "%LOCALAPPDATA%\miniconda3\envs\chinese-ocr\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\miniconda3\envs\chinese-ocr\python.exe"
    goto :found
)
:: 5. System-wide C:\miniconda3
if exist "C:\miniconda3\envs\chinese-ocr\python.exe" (
    set "PY_EXE=C:\miniconda3\envs\chinese-ocr\python.exe"
    goto :found
)
:: 6. ProgramData Miniconda
if exist "C:\ProgramData\miniconda3\envs\chinese-ocr\python.exe" (
    set "PY_EXE=C:\ProgramData\miniconda3\envs\chinese-ocr\python.exe"
    goto :found
)

:: Not found in any standard location
echo.
echo  ============================================================
echo  [ERROR] Could not find the 'chinese-ocr' conda environment.
echo  ============================================================
echo.
echo  Expected python.exe at one of:
echo    %%USERPROFILE%%\miniconda3\envs\chinese-ocr\python.exe
echo    %%USERPROFILE%%\anaconda3\envs\chinese-ocr\python.exe
echo.
echo  To fix:
echo    1. Open PowerShell
echo    2. Run: .\install.ps1
echo    3. Try run.bat again
echo.
pause
exit /b 1

:found
echo  Using: %PY_EXE%
echo  Starting Simplified Chinese OCR App...
echo.

"%PY_EXE%" main.py

if %errorlevel% neq 0 (
    echo.
    echo  ============================================================
    echo  [ERROR] App exited with error code %errorlevel%.
    echo  ============================================================
    echo.
    echo  Common causes:
    echo    - config.json missing: copy config.example.json config.json
    echo    - Missing packages:    run install.ps1 to repair
    echo    - Check the log output above for details
    echo.
    pause
)
endlocal
