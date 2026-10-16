@echo off
setlocal
REM ============================================================
REM  vibe - stop a server started by start.bat
REM
REM  The normal way is Ctrl+C in the window that started it. This exists for a
REM  server left running in the background, or for a window the user cannot
REM  find: nobody should have to open Task Manager to stop their own app.
REM
REM  stop.bat [port]   - default: the port start.bat recorded, else 7321
REM ============================================================

set "PORT=%~1"
if not "%PORT%"=="" goto have_port
if exist "%TEMP%\vibe-port.txt" set /p PORT=<"%TEMP%\vibe-port.txt"
if "%PORT%"=="" set "PORT=7321"
:have_port

echo Asking the vibe server on port %PORT% to stop...
curl.exe -s -X POST -o NUL --max-time 5 "http://127.0.0.1:%PORT%/admin/shutdown"
if errorlevel 1 (
    echo No vibe server answered on port %PORT%.
    echo If it runs on another port, name it: stop.bat ^<port^>
    exit /b 1
)

REM A server that accepted the request but kept listening would leave a process
REM the user cannot see, so the closed port is the proof, not the response.
for /l %%i in (1,1,20) do (
    curl.exe -s -f -o NUL --max-time 1 "http://127.0.0.1:%PORT%/health" 2>nul
    if errorlevel 1 (
        echo vibe stopped; port %PORT% is free.
        del "%TEMP%\vibe-port.txt" >nul 2>&1
        exit /b 0
    )
    timeout /t 1 /nobreak >nul
)
echo The server accepted the request but port %PORT% is still listening after 20s.
exit /b 1
