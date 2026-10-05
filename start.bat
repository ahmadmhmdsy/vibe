@echo off
REM ============================================================
REM  vibe - start backend + frontend dev servers
REM  Double-click to launch both servers in separate windows.
REM ============================================================

set VIBE_PORT=7321
set VIBE_CORS_ORIGINS=http://localhost:5173,http://localhost:5174

REM --- Check if the port is free; if not, find the next available ---
for /f "delims=" %%p in ('powershell -NoProfile -Command "$p=%VIBE_PORT%; while (Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue) { $p++ }; Write-Output $p"') do set VIBE_PORT=%%p

echo Starting backend on port %VIBE_PORT%...
start "vibe-backend" cmd /k "cd /d "%~dp0services\vibe" && .venv\Scripts\python.exe -m uvicorn vibe.api.app:create_app --factory --port %VIBE_PORT%"

echo Starting frontend dev server...
start "vibe-frontend" cmd /k "cd /d "%~dp0apps\vibe" && set VITE_API_URL=http://localhost:%VIBE_PORT%&& pnpm run dev"

echo.
echo ========================================
echo   Backend:  http://localhost:%VIBE_PORT%
echo   Frontend: http://localhost:5173 (Vite)
echo ========================================
echo.
echo Press Ctrl+C in each window to stop a server.
pause
