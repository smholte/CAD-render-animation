@echo off
rem Removes Fresing Render. Projects and renders are kept.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Uninstall-FresingRender.ps1" %*
echo.
pause
