@echo off
chcp 65001 >nul 2>&1

echo.
echo ========================================
echo   tailorCV Service Restart Tool v2.0
echo   Enhanced - Thorough Cleanup
echo ========================================
echo.

:: Step 1: Kill ALL Python processes
echo [1/4] Terminating Python processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
echo   - Done
echo.

:: Step 2: Release ports
echo [2/4] Releasing ports...
powershell -ExecutionPolicy Bypass -File "%~dp0kill_ports.ps1"
echo.

:: Step 3: Clear all caches
echo [3/4] Clearing caches...

:: Clear __pycache__ directories
for /d /r "%~dp0" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d" 2>nul
)
echo   - __pycache__ cleared

:: Clear .pyc files
del /s /q "%~dp0*.pyc" >nul 2>&1
echo   - .pyc files cleared

:: Clear other cache directories
if exist "%~dp0.cache" rd /s /q "%~dp0.cache" 2>nul
if exist "%~dp0.pytest_cache" rd /s /q "%~dp0.pytest_cache" 2>nul
if exist "%~dp0.mypy_cache" rd /s /q "%~dp0.mypy_cache" 2>nul
echo   - Other caches cleared

timeout /t 1 /nobreak >nul
echo.

:: Step 4: Start service
echo [4/4] Starting service...
echo.
echo ========================================
echo   tailorCV Resume Tool
echo   URL: http://localhost:6001
echo ========================================
echo.

python "%~dp0run_simple.py"
