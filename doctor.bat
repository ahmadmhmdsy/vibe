@echo off
REM R5-T1 - preflight. Prints one PASS/FAIL per prerequisite and, under each
REM failure, the exact command that fixes it. Exit code 1 means a blocking
REM problem, so start.bat can stop before launching anything (wiring it
REM into start.bat is R5-T2; today start.bat launches uvicorn directly).
setlocal
set "PY=%~dp0services\vibe\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo FAIL  python-venv   missing %PY%
  echo       -^> create it: python -m venv "%~dp0services\vibe\.venv"
  exit /b 1
)
"%PY%" -m vibe doctor
exit /b %errorlevel%
