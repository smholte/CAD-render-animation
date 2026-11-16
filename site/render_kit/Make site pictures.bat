@echo off
rem Fresing Render - pictures and videos for the web page (tasks 0047, 0112).
rem Double-click. Needs Fresing Render installed (Install.bat). Reads models.ini, the STEP files in the
rem "models" folder next to this file (or in the first kit's, next to this folder) and the projects folder;
rem writes everything to the "output" folder next to this file. Task 0144: a start window (kit_window.ps1) asks how hard
rem the graphics card may work, which models, when to start and what happens at the end, and offers to continue a run
rem that stopped; a small status window has Pause / Stop. Without the window the questions come in this console.
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
if not exist "%OUT%\" mkdir "%OUT%"
set "EST=%TEMP%\fresing_site_kit_estimate.json"
set "CHOICES=%OUT%\run_choices.json"
if exist "%EST%" del "%EST%"
"%BLENDER%" --background --python-exit-code 3 --python "%KIT%make_site_pictures.py" -- "%MODELS%" "%OUT%" "%KIT%models.ini" "--estimate-json=%EST%"
if not "%ERRORLEVEL%"=="0" (
    echo.
    echo models.ini has a problem: see the line above. Fix it in Notepad and double-click this file again.
    echo.
    pause
    exit /b 2
)
echo.
echo The start window opens now. Choose there and click Start.
if exist "%CHOICES%" del "%CHOICES%"
if exist "%OUT%\run_result.txt" del "%OUT%\run_result.txt"
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%KIT%kit_window.ps1" -Mode start -Estimate "%EST%" -Choices "%CHOICES%"
set "WIN=%ERRORLEVEL%"
if "%WIN%"=="10" (
    echo Cancelled: nothing was started.
    exit /b 0
)
if "%WIN%"=="0" if exist "%CHOICES%" goto with_window

rem --- no start window: the questions in this console (as before task 0144) ---
set "WIN=none"
echo.
echo The start window could not open ^(see the line above^): the questions come here instead.
echo The graphics-card load and the quiet hours saved as the standard are used.
set "START="
set /p "START=Start now: press Enter. Start later: type a time like 23:30 and press Enter: "
rem a typed quote would break the quoting below; the time itself goes in quotes (spaces, & or | stay text)
if defined START set "START=%START:"=%"
echo.
echo You can keep working; close this window to stop.
echo.
"%BLENDER%" --background --python-exit-code 3 --python "%KIT%make_site_pictures.py" -- "%MODELS%" "%OUT%" "%KIT%models.ini" "--start-at=%START%" --ask-resume
set "CODE=%ERRORLEVEL%"
if exist "%OUT%\run_result.txt" set /p CODE=<"%OUT%\run_result.txt"
goto finished

:with_window
if exist "%OUT%\status.json" del "%OUT%\status.json"
>"%OUT%\control.txt" echo run
start "Fresing status" powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%KIT%kit_window.ps1" -Mode status -Out "%OUT%"
echo.
echo Running. The small status window shows how far it is and has Pause and Stop.
echo You can keep working; closing this black window stops the run too (double-click again: it offers to continue it).
echo.
"%BLENDER%" --background --python-exit-code 3 --python "%KIT%make_site_pictures.py" -- "%MODELS%" "%OUT%" "%KIT%models.ini" "--choices=%CHOICES%"
set "CODE=%ERRORLEVEL%"
if exist "%OUT%\run_result.txt" set /p CODE=<"%OUT%\run_result.txt"
>"%OUT%\control.txt" echo ended

:finished
echo.
set "KNOWN="
if "%CODE%"=="0" set "KNOWN=1"
if "%CODE%"=="1" set "KNOWN=1"
if "%CODE%"=="2" set "KNOWN=1"
if "%CODE%"=="3" set "KNOWN=1"
if "%CODE%"=="0" (
    echo Done. The output folder opens now: upload site_pictures_^<date^>.zip ^(README.txt, step 7^).
) else if "%CODE%"=="4" (
    echo Stopped. What is done is in the output folder. Double-click this file again and tick
    echo "Continue the run" to make the rest ^(in this console: answer Y when it asks^).
) else if defined KNOWN (
    echo Finished with problems ^(code %CODE%^): see log.txt in the output folder. The zip holds what was made.
) else (
    echo Blender stopped unexpectedly ^(code %CODE%^). Double-click this file again: it offers to continue the run, or
    echo upload output\log.txt ^(README.txt, step 7^) and blender.crash.txt from the folder "%TEMP%" if it is there.
)
if exist "%OUT%\" start "" explorer "%OUT%"
if exist "%OUT%\contact_sheet.html" start "" "%OUT%\contact_sheet.html"
if "%WIN%"=="0" powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%KIT%kit_window.ps1" -Mode end -Choices "%CHOICES%" -Code %CODE%
echo.
pause
exit /b %CODE%
