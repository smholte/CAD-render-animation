@echo off
rem Fresing Render - pictures and videos for the web page (tasks 0047, 0112).
rem Double-click. Needs Fresing Render installed (Install.bat). Reads models.ini, the STEP files in the
rem "models" folder next to this file (or in the first kit's, next to this folder) and the projects folder;
rem writes everything to the "output" folder next to this file. Shows the expected time, then asks when to start.
setlocal EnableExtensions
title Fresing site pictures
set "KIT=%~dp0"
set "MODELS=%KIT%models"
set "OUT=%KIT%output"

if not exist "%KIT%models.ini" (
    echo.
    echo Unzip the kit first: right-click the zip, Extract All..., then open the new folder
    echo and double-click "Make site pictures.bat" there.
    echo.
    pause
    exit /b 1
)

set "INSTALL=%LOCALAPPDATA%\FresingRender"
set "BLENDER="
for /d %%D in ("%INSTALL%\blender-*-windows-x64") do (
    if exist "%%~fD\blender.exe" set "BLENDER=%%~fD\blender.exe"
)
if not defined BLENDER (
    echo.
    echo Fresing Render is not installed on this PC: no blender.exe in "%INSTALL%".
    echo Install it first: unzip the installer and double-click Install.bat.
    echo.
    pause
    exit /b 1
)
if not exist "%MODELS%\" (
    mkdir "%MODELS%"
    echo.
    echo A "models" folder was made next to this file. Put the STEP files in it
    echo with the names that models.ini gives ^(file = ...^), then double-click this file again.
    echo.
    start "" explorer "%MODELS%"
    pause
    exit /b 1
)

echo.
echo Making the pictures and the videos for the web page.
"%BLENDER%" --background --python-exit-code 3 --python "%KIT%make_site_pictures.py" -- "%MODELS%" "%OUT%" "%KIT%models.ini" --estimate-only
if not "%ERRORLEVEL%"=="0" (
    echo.
    echo models.ini has a problem: see the line above. Fix it in Notepad and double-click this file again.
    echo.
    pause
    exit /b 2
)
echo.
set "START="
set /p "START=Start now: press Enter. Start later: type a time like 23:30 and press Enter: "
rem a typed quote would break the quoting below; the time itself goes in quotes (spaces, & or | stay text)
if defined START set "START=%START:"=%"
echo.
echo You can keep working; close this window to stop.
echo.
"%BLENDER%" --background --python-exit-code 3 --python "%KIT%make_site_pictures.py" -- "%MODELS%" "%OUT%" "%KIT%models.ini" "--start-at=%START%"
set "CODE=%ERRORLEVEL%"
echo.
set "KNOWN="
if "%CODE%"=="0" set "KNOWN=1"
if "%CODE%"=="1" set "KNOWN=1"
if "%CODE%"=="2" set "KNOWN=1"
if "%CODE%"=="3" set "KNOWN=1"
if "%CODE%"=="0" (
    echo Done. The output folder opens now: upload site_pictures_^<date^>.zip ^(README.txt, step 6^).
) else if defined KNOWN (
    echo Finished with problems ^(code %CODE%^): see log.txt in the output folder. The zip holds what was made.
) else (
    echo Blender stopped unexpectedly ^(code %CODE%^). Upload output\log.txt ^(README.txt, step 6^),
    echo and blender.crash.txt from the folder "%TEMP%" if it is there.
)
if exist "%OUT%\" start "" explorer "%OUT%"
if exist "%OUT%\contact_sheet.html" start "" "%OUT%\contact_sheet.html"
echo.
pause
exit /b %CODE%
