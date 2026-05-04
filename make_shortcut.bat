@echo off
:: make_shortcut.bat — Creates a "Simplified Chinese OCR" shortcut on the Desktop.
:: Run this once after install.ps1.

setlocal

set "PROJECT_DIR=%~dp0"
:: Remove trailing backslash
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

set "SHORTCUT_NAME=Simplified Chinese OCR"
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\%SHORTCUT_NAME%.lnk"
set "TARGET=%PROJECT_DIR%\run.bat"
set "ICON=%PROJECT_DIR%\run.bat"

echo Creating Desktop shortcut: %SHORTCUT%

:: Write a VBScript to create the .lnk file
set "VBS=%TEMP%\make_ocr_shortcut.vbs"
(
    echo Set oWS = WScript.CreateObject^("WScript.Shell"^)
    echo sLinkFile = "%SHORTCUT%"
    echo Set oLink = oWS.CreateShortcut^(sLinkFile^)
    echo oLink.TargetPath = "%TARGET%"
    echo oLink.WorkingDirectory = "%PROJECT_DIR%"
    echo oLink.Description = "Simplified Chinese OCR App"
    echo oLink.Save
) > "%VBS%"

cscript //nologo "%VBS%"
del "%VBS%" >nul 2>&1

if exist "%SHORTCUT%" (
    echo.
    echo  [OK] Shortcut created: %SHORTCUT%
    echo  Double-click "Simplified Chinese OCR" on your Desktop to launch the app.
) else (
    echo.
    echo  [ERROR] Shortcut creation failed.
    echo  You can launch the app by double-clicking run.bat in:
    echo    %PROJECT_DIR%
)

echo.
pause
endlocal
