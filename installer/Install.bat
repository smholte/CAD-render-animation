@echo off
rem Fresing Render installer: double-click to install, repair or upgrade.
rem Optional: Install.bat -UpdateUrl https://.../index.json -AccessToken XXXX
if not exist "%~dp0Install-FresingRender.ps1" (
  echo Please unzip the whole folder first, then run Install.bat from the unzipped folder.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-FresingRender.ps1" %*
echo.
pause
