@echo off
echo Stopping Llama.cpp GUI...
taskkill /f /im python.exe /t >nul 2>&1
echo Stopped.
pause
