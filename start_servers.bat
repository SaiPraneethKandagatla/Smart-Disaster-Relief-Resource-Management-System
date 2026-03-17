@echo off
echo Starting Relief System Servers...
echo.

cd /d "C:\Users\DELL\OneDrive\Desktop\AIAC"

echo Starting HelpDesk (port 5000)...
start "HelpDesk" python web_app.py

timeout /t 2 >nul

echo Starting Admin Portal (port 5001)...
start "Admin Portal" python admin_app.py

timeout /t 3 >nul

echo.
echo Opening in Chrome...
start chrome http://127.0.0.1:5000
start chrome http://127.0.0.1:5001

echo.
echo Servers running! Close the terminal windows to stop them.
pause
