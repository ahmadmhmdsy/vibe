@echo off
setlocal
REM ============================================================
REM  vibe - one command, one window, one port
REM
REM    start.bat        production: FastAPI serves the built app AND the API
REM                     on one loopback port. Ctrl+C stops everything.
REM    start.bat dev    development: Vite serves the frontend with hot reload,
REM                     the API keeps this window.
REM    start.bat backup opt-in: snapshot the workspace with "vibe backup"
REM                     before serving, so a bad start cannot lose your work.
REM
REM  The old version always opened two windows, never checked the machine and
REM  hard-coded port 7321, so closing one window left the other running.
REM ============================================================

set "ROOT=%~dp0"
set "PY=%ROOT%services\vibe\.venv\Scripts\python.exe"
set "MODE=prod"
set "BACKUP="
if /i "%~1"=="dev" set "MODE=dev"
if /i "%~1"=="backup" set "BACKUP=1"

REM --- 1. Preflight: one clear sentence beats a stack trace. ---
echo Checking this machine before starting...
call "%ROOT%doctor.bat"
if errorlevel 1 (
    echo.
    echo Start stopped: fix the blocking problems listed above, then run start.bat again.
    exit /b 1
)

REM --- 2. Opt-in backup: --keep 7 keeps the newest 7 snapshots. ---
if defined BACKUP (
    echo Backing up the workspace before starting...
    "%PY%" -m vibe backup --keep 7
    if errorlevel 1 (
        echo.
        echo Start stopped: the backup failed, so nothing was changed. Fix the problem above and retry.
        exit /b 1
    )
)

REM --- 3. A free port, so a stale server cannot make this look broken. ---
set "VIBE_PORT=7321"
for /f "delims=" %%p in ('powershell -NoProfile -Command "$p=7321; while (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { $p++ }; Write-Output $p"') do set "VIBE_PORT=%%p"
> "%TEMP%\vibe-port.txt" echo %VIBE_PORT%

set "VIBE_HOST=127.0.0.1"
set "VIBE_MODE=%MODE%"
set "VIBE_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:%VIBE_PORT%,http://127.0.0.1:%VIBE_PORT%"
set "VITE_API_URL=http://127.0.0.1:%VIBE_PORT%"
if /i "%MODE%"=="prod" (set "URL=http://127.0.0.1:%VIBE_PORT%/") else (set "URL=http://localhost:5173/")

if /i "%MODE%"=="dev" (
    REM Vite needs its own process and its own console: it owns the HMR socket
    REM and the frontend build. Production needs neither, which is exactly why
    REM production is the default.
    echo Starting the Vite dev server in its own window...
    start "vibe-frontend" cmd /k "cd /d "%ROOT%apps\vibe" && pnpm run dev"
)

echo.
echo   mode   %MODE%
echo   api    http://127.0.0.1:%VIBE_PORT%
echo   open   %URL%
echo   stop   Ctrl+C here, or run stop.bat from another window
echo.

REM --- 4. Open the browser as soon as /health answers, never before. ---
start "" /b powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ curl.exe -s -f -o NUL --max-time 2 'http://127.0.0.1:%VIBE_PORT%/health' 2>$null; if($LASTEXITCODE -eq 0){ Start-Process '%URL%'; $ok=$true; break }; Start-Sleep -Seconds 1 }; if(-not $ok){ Write-Host ''; Write-Host 'vibe did not answer /health within 30s - open %URL% yourself' }"

REM --- 5. The server runs in THIS window, so Ctrl+C stops it and its children. ---
"%PY%" -m vibe serve
set "CODE=%ERRORLEVEL%"

echo.
if not "%CODE%"=="0" (
    echo vibe exited with code %CODE%. Run doctor.bat to see what is missing.
    pause
) else (
    echo vibe stopped.
)
exit /b %CODE%
