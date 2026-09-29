@echo off
REM ============================================================
REM  vibe - run all tests (backend + frontend)
REM ============================================================

echo Running backend tests...
cd /d E:\python_projects\apps_building\services\vibe
.venv\Scripts\python.exe -m pytest -q
if %errorlevel% neq 0 (
  echo.
  echo BACKEND TESTS FAILED
  pause
  exit /b %errorlevel%
)

echo.
echo Running frontend tests...
cd /d E:\python_projects\apps_building\apps\vibe
call pnpm test --run
if %errorlevel% neq 0 (
  echo.
  echo FRONTEND TESTS FAILED
  pause
  exit /b %errorlevel%
)

echo.
echo ========================================
echo   All tests passed!
echo ========================================
pause
