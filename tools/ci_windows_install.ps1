<#
.SYNOPSIS
  Windows install test for the automatic tests on GitHub: does what the owner does, unattended.

.DESCRIPTION
  1. Unzips the installer zip into a folder whose name has a space and an accent (like a
     Downloads folder), puts the cached Blender zip next to Install.bat.
  2. Points LOCALAPPDATA at a user folder with a space and an accent, so Install.bat installs to
     its default place (%LOCALAPPDATA%\FresingRender) exactly as on a double-click.
  3. Runs Install.bat twice (install, then repair over the existing install) with no keyboard
     (its "press a key" pause gets an empty input).
  4. Checks what the installer must leave behind: Blender, the extension with the right version,
     the app template, the shortcuts, installed.txt.
  5. Starts the self-test exactly as the Start-menu shortcut "Fresing Render - Self test" does
     and copies its report to -OutDir. The report is judged afterwards by tools/ci_check_selftest.py.
  With -Uninstall it instead runs Uninstall.bat and checks that everything is gone.

  Run with FRESING_SELFTEST_NO_GPU=1 on machines without a graphics card.

.EXAMPLE
  pwsh tools/ci_windows_install.ps1 -ReleaseZip dist\FresingRender-0.2.8-windows.zip -BlenderZip C:\cache\blender-5.2.3-windows-x64.zip -WorkDir C:\t -OutDir C:\t\out
#>
[CmdletBinding()]
param(
    [string]$ReleaseZip,
    [string]$BlenderZip,
    [Parameter(Mandatory)] [string]$WorkDir,
    [Parameter(Mandatory)] [string]$OutDir,
    [int]$SelfTestMinutes = 15,      # measured: about 1.5-2 minutes on GitHub's runner
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
New-Item -ItemType Directory -Force -Path $WorkDir, $OutDir | Out-Null
$WorkDir = (Resolve-Path -LiteralPath $WorkDir).Path
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path

# Folders a real user could have: a space and an accent in both.
$UnzipDir = Join-Path $WorkDir "Mijn downloads é"
$LocalAppData = Join-Path $WorkDir "Users\Sébastien Test\AppData\Local"
$InstallDir = Join-Path $LocalAppData "FresingRender"
$Desktop = [Environment]::GetFolderPath("Desktop")
$Programs = [Environment]::GetFolderPath("Programs")
$Summary = @()
$Problems = @()

function Note([string]$text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Problem([string]$text) {
    $script:Problems += $text
    Write-Host "::error title=Windows install::$text"
}

function Run-Bat([string]$Bat, [string]$LogName, [int]$Minutes = 10) {   # measured: 3-21 s
    # The .bat ends with "pause": an empty file as keyboard input ends the pause at once.
    $empty = Join-Path $WorkDir "no_keyboard.txt"
    Set-Content -LiteralPath $empty -Value "" -NoNewline
    $log = Join-Path $OutDir "$LogName.log"
    $err = Join-Path $OutDir "$LogName.stderr.log"
    $t0 = Get-Date
    # The .bat starts Windows PowerShell 5.1. A PSModulePath inherited from PowerShell 7 (this
    # script) makes 5.1 load the wrong modules; a double-click from Explorer has none of that.
    $savedModulePath = $env:PSModulePath
    Remove-Item Env:PSModulePath -ErrorAction SilentlyContinue
    try {
        $p = Start-Process -FilePath $Bat -WorkingDirectory (Split-Path -Parent $Bat) -NoNewWindow -PassThru `
            -RedirectStandardInput $empty -RedirectStandardOutput $log -RedirectStandardError $err
    } finally {
        $env:PSModulePath = $savedModulePath
    }
    $null = $p.Handle   # keeps the exit code readable after the process ends
    if (-not $p.WaitForExit($Minutes * 60 * 1000)) {
        & taskkill /T /F /PID $p.Id | Out-Null
        Problem "$LogName did not finish within $Minutes minutes (waiting for input?)"
    }
    $secs = [math]::Round(((Get-Date) - $t0).TotalSeconds)
    Write-Host "----- $LogName output -----"
    Get-Content -LiteralPath $log | ForEach-Object { Write-Host "   $_" }
    Get-Content -LiteralPath $err -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "   (stderr) $_" }
    return @{ Code = $p.ExitCode; Seconds = $secs; Text = (Get-Content -LiteralPath $log -Raw) }
}

$env:LOCALAPPDATA = $LocalAppData
New-Item -ItemType Directory -Force -Path $LocalAppData | Out-Null

if ($Uninstall) {
    $bat = Get-ChildItem -LiteralPath $UnzipDir -Recurse -Filter "Uninstall.bat" | Select-Object -First 1
    if (-not $bat) { throw "Uninstall.bat not found under $UnzipDir (run the install part first)" }
    Note "Uninstall.bat"
    $r = Run-Bat $bat.FullName "uninstall" 5
    if (Test-Path -LiteralPath $InstallDir) { Problem "Uninstall left $InstallDir behind" }
    if (Test-Path -LiteralPath (Join-Path $Desktop "Fresing Render.lnk")) { Problem "Uninstall left the Desktop shortcut" }
    if (Test-Path -LiteralPath (Join-Path $Programs "Fresing Render")) { Problem "Uninstall left the Start-menu folder" }
    if ($r.Text -notmatch "Fresing Render removed") { Problem "Uninstall did not say 'Fresing Render removed'" }
    $Summary += "| Uninstall.bat | $(if ($Problems) { '❌' } else { '✅' }) exit code $($r.Code) | $($r.Seconds) s |"
} else {
    # ---- 1. unzip like a user -------------------------------------------------------
    if (Test-Path -LiteralPath $UnzipDir) { Remove-Item -LiteralPath $UnzipDir -Recurse -Force }
    Note "Unzipping $(Split-Path -Leaf $ReleaseZip) into '$UnzipDir'"
    Expand-Archive -LiteralPath $ReleaseZip -DestinationPath $UnzipDir
    $bat = Get-ChildItem -LiteralPath $UnzipDir -Recurse -Filter "Install.bat" | Select-Object -First 1
    if (-not $bat) { throw "Install.bat not found in $ReleaseZip" }
    $Here = $bat.DirectoryName
    $zipExt = Get-ChildItem -LiteralPath $Here -Filter "fresing_render-*.zip" | Select-Object -First 1
    if (-not $zipExt) { throw "fresing_render-<version>.zip not found in $ReleaseZip" }
    $Expected = [regex]::Match($zipExt.Name, '^fresing_render-(\d+(\.\d+)*)').Groups[1].Value
    if (-not $Expected) { throw "no version in the name $($zipExt.Name)" }
    Note "Version in the zip: $Expected"
    if ($BlenderZip) { Copy-Item -LiteralPath $BlenderZip -Destination $Here }

    # ---- 2. install twice: fresh, then repair over it ----------------------------------
    foreach ($round in @("install", "repair")) {
        Note "Install.bat ($round)"
        $r = Run-Bat $bat.FullName $round
        $done = $r.Text -match "Done\. Start 'Fresing Render' from the Desktop\."
        $ok = $done -and ($r.Code -eq 0)
        if (-not $done) { Problem "Install.bat ($round) did not reach 'Done.' - see $round.log" }
        if ($r.Code -ne 0) { Problem "Install.bat ($round) ended with exit code $($r.Code)" }
        $Summary += "| Install.bat ($round) | $(if ($ok) { '✅' } else { '❌' }) exit code $($r.Code) | $($r.Seconds) s |"
        if (-not $ok) { break }
    }

    # ---- 3. what the installer must leave behind ------------------------------------
    $BlenderExe = Get-ChildItem -LiteralPath $InstallDir -Recurse -Filter "blender.exe" -Depth 1 -ErrorAction SilentlyContinue | Select-Object -First 1
    $checks = [ordered]@{
        "Blender program"          = [bool]$BlenderExe
        "installed.txt"            = Test-Path -LiteralPath (Join-Path $InstallDir "installed.txt")
        "Desktop shortcut"         = Test-Path -LiteralPath (Join-Path $Desktop "Fresing Render.lnk")
        "Start-menu shortcut"      = Test-Path -LiteralPath (Join-Path $Programs "Fresing Render\Fresing Render.lnk")
        "Self-test shortcut"       = Test-Path -LiteralPath (Join-Path $Programs "Fresing Render\Fresing Render - Self test.lnk")
    }
    if ($BlenderExe) {
        $portable = Join-Path $BlenderExe.DirectoryName "portable"
        $manifest = Join-Path $portable "extensions\user_default\fresing_render\blender_manifest.toml"
        $ver = ""
        if (Test-Path -LiteralPath $manifest) {
            $ver = [regex]::Match((Get-Content -LiteralPath $manifest -Raw), '(?m)^version\s*=\s*"([^"]+)"').Groups[1].Value
        }
        $checks["Extension $Expected installed (found '$ver')"] = ($ver -eq $Expected)
        $checks["App template"] = Test-Path -LiteralPath (Join-Path $portable "scripts\startup\bl_app_templates_user\fresing_render\__init__.py")
        $checks["Preferences saved"] = Test-Path -LiteralPath (Join-Path $portable "config\userpref.blend")
    }
    foreach ($k in $checks.Keys) {
        if (-not $checks[$k]) { Problem "missing after install: $k" }
        $Summary += "| $k | $(if ($checks[$k]) { '✅' } else { '❌' }) | |"
    }

    # ---- 4. the self-test, started exactly like its Start-menu shortcut -------------------
    $lnkPath = Join-Path $Programs "Fresing Render\Fresing Render - Self test.lnk"
    if (Test-Path -LiteralPath $lnkPath) {
        $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut($lnkPath)
        Note "Self-test: `"$($lnk.TargetPath)`" $($lnk.Arguments)"
        $report = Join-Path $Desktop "Fresing Render self-test.txt"
        Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue
        $log = Join-Path $OutDir "selftest_blender.log"
        $t0 = Get-Date
        $p = Start-Process -FilePath $lnk.TargetPath -ArgumentList $lnk.Arguments -WorkingDirectory $lnk.WorkingDirectory `
            -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError (Join-Path $OutDir "selftest_blender.stderr.log")
        $null = $p.Handle
        if (-not $p.WaitForExit($SelfTestMinutes * 60 * 1000)) {
            & taskkill /T /F /PID $p.Id | Out-Null
            Problem "the self-test did not finish within $SelfTestMinutes minutes"
        }
        $secs = [math]::Round(((Get-Date) - $t0).TotalSeconds)
        Write-Host "----- self-test output -----"
        Get-Content -LiteralPath $log | ForEach-Object { Write-Host "   $_" }
        if (Test-Path -LiteralPath $report) {
            Copy-Item -LiteralPath $report -Destination (Join-Path $OutDir "Fresing Render self-test.txt")
        } else {
            Problem "the self-test wrote no report on the Desktop"
        }
        $renders = Join-Path $Desktop "Fresing Render self-test"
        if (Test-Path -LiteralPath $renders) { Copy-Item -LiteralPath $renders -Destination (Join-Path $OutDir "renders") -Recurse }
        $Summary += "| Self-test (Start-menu shortcut) | finished, judged below | $secs s |"
    }
}

$table = @("### Windows install ($(if ($Uninstall) { 'uninstall' } else { 'install' })): $(if ($Problems) { 'FAILED' } else { 'passed' })", "",
           "| Step | Result | Time |", "| --- | --- | --- |") + $Summary
if ($Problems) { $table += @("", "**Problems:**", "") + ($Problems | ForEach-Object { "- $_" }) }
$text = ($table -join "`n") + "`n"
Write-Host $text
if ($env:GITHUB_STEP_SUMMARY) { Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Value $text -Encoding utf8 }
if ($Problems) { exit 1 }
