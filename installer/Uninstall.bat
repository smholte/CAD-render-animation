@echo off
rem Removes Fresing Render. Projects and renders are kept. Asks Y/N first (-Ask, task 0339).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Uninstall-FresingRender.ps1" -Ask %*
echo.
pause
