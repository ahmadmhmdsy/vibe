@echo off
REM ============================================================
REM  vibe - start backend + frontend dev servers
REM  Double-click to launch both servers in separate windows.
REM ============================================================

set VIBE_PORT=8123

echo Starting backend on port %VIBE_PORT%...
start "vibe-backend" cmd /k "cd /d E:\python_projects\apps_building\services\vibe && .venv\Scripts\python.exe -m uvicorn vibe.api.app:create_app --factory --port %VIBE_PORT%"

echo Starting frontend dev server...
start "vibe-frontend" cmd /k "cd /d E:\python_projects\apps_building\apps\vibe && set VITE_API_URL=http://localhost:%VIBE_PORT% && pnpm run dev"

echo.
echo ========================================
echo   Backend:  http://localhost:%VIBE_PORT%
echo   Frontend: http://localhost:5173 (Vite)
echo ========================================
echo.
echo Press Ctrl+C in each window to stop a server.
pause
