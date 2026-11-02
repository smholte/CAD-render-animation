@echo off
rem Fresing Render installer: double-click to install or repair.
rem Optional: Install.bat -UpdateUrl https://.../index.json -AccessToken XXXX
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-FresingRender.ps1" %*
echo.
pause
