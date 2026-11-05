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
  6. Starts the PC check (Full) exactly as its Start-menu shortcut does and copies its report and its
     text block (pccheck_last_run.txt) to -OutDir; judged afterwards by tools/ci_check_pccheck.py.
  With -Uninstall it instead runs Uninstall.bat and checks that everything is gone.

  In-app update (task 0020), before step 2 when -OldReleaseZip is given:
  U1. Install.bat of an old build (the same code as version 0.0.1 with the app template of 0.2.10),
      fresh, with -UpdateUrl pointing at -UpdateRepo (a local copy of the update listing, in a folder with
      a space and an accent) - or, with -UpdateFrom github, at the real newest release on GitHub.
  U2. The old app (in the background) runs tools/update_test_blender.py: it must find -Expect, press
      Update now and close; update_helper.py installs the update and starts the app again with "-- after",
      which checks the new version, the message and the app template.
  U3. Checks the files: installed version, app template = the new one, update log, the user-guide shortcut.
  Then steps 2-5 run over the updated install (-OnlyUpdate stops after U3: the release check).

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
    [int]$PcCheckMinutes = 30,       # the PC check, Full (task 0032)
    [switch]$Uninstall,
    [string]$OldReleaseZip,          # in-app update test: install this first, then update it in the app
    [string]$UpdateRepo,             # ...from this local update listing (index.json + zip + changelog.json)
    [string]$UpdateFrom = "",        # ...or from this address ("github" = the newest release on GitHub)
    [string]$Expect = "",            # the version the update must bring (default: the one in -ReleaseZip)
    [switch]$OnlyUpdate
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

function Run-Bat([string]$Bat, [string]$LogName, [int]$Minutes = 10, [string]$Arguments = "") {   # measured: 3-21 s
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
        $more = @{}
        if ($Arguments) { $more["ArgumentList"] = $Arguments }
        $p = Start-Process -FilePath $Bat -WorkingDirectory (Split-Path -Parent $Bat) -NoNewWindow -PassThru `
            -RedirectStandardInput $empty -RedirectStandardOutput $log -RedirectStandardError $err @more
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
    if (-not $OnlyUpdate) {
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
    }
    if (-not $Expect) { $Expect = $Expected }

    # ---- U. in-app update: an old version updates itself ------------------------------
    if ($OldReleaseZip) {
        $OldDir = Join-Path $WorkDir "Oude versie é"
        if (Test-Path -LiteralPath $OldDir) { Remove-Item -LiteralPath $OldDir -Recurse -Force }
        Note "Unzipping the old build $(Split-Path -Leaf $OldReleaseZip) into '$OldDir'"
        Expand-Archive -LiteralPath $OldReleaseZip -DestinationPath $OldDir
        $oldBat = Get-ChildItem -LiteralPath $OldDir -Recurse -Filter "Install.bat" | Select-Object -First 1
        if ($BlenderZip) { Copy-Item -LiteralPath $BlenderZip -Destination $oldBat.DirectoryName }
        $oldZipExt = Get-ChildItem -LiteralPath $oldBat.DirectoryName -Filter "fresing_render-*.zip" | Select-Object -First 1
        $OldVersion = [regex]::Match($oldZipExt.Name, '^fresing_render-(\d+(\.\d+)*)').Groups[1].Value
        $url = ""
        if ($UpdateRepo) {
            $repoCopy = Join-Path $WorkDir "update listing é"
            if (Test-Path -LiteralPath $repoCopy) { Remove-Item -LiteralPath $repoCopy -Recurse -Force }
            Copy-Item -LiteralPath $UpdateRepo -Destination $repoCopy -Recurse
            $url = ([Uri](Join-Path $repoCopy "index.json")).AbsoluteUri
        } elseif ($UpdateFrom -and $UpdateFrom -ne "github") {
            $url = $UpdateFrom
        }
        Note "Install.bat of version $OldVersion, update address: $(if ($url) { $url } else { 'GitHub (default)' })"
        $r = Run-Bat $oldBat.FullName "install-old" 10 $(if ($url) { "-UpdateUrl `"$url`"" } else { "" })
        $ok = ($r.Code -eq 0) -and ($r.Text -match "Done\. Start 'Fresing Render' from the Desktop\.")
        if (-not $ok) { Problem "Install.bat of the old version failed (exit code $($r.Code)) - see install-old.log" }
        $Summary += "| Install.bat (old version $OldVersion, fresh) | $(if ($ok) { '✅' } else { '❌' }) exit code $($r.Code) | $($r.Seconds) s |"

        $exe = Get-ChildItem -LiteralPath $InstallDir -Recurse -Filter "blender.exe" -Depth 1 -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($ok -and $exe) {
            $portable = Join-Path $exe.DirectoryName "portable"
            $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
            $script = Join-Path $repoRoot "tools\update_test_blender.py"
            $before = Join-Path $OutDir "update_before.json"
            $after = Join-Path $OutDir "update_after.json"
            Remove-Item -LiteralPath $before, $after -Force -ErrorAction SilentlyContinue
            $env:UPDATE_TEST_EXPECT = $Expect
            $env:UPDATE_TEST_OLD = $OldVersion
            $env:UPDATE_TEST_PROJECT = Join-Path $WorkDir "Projecten é\Kraan – update test.blend"
            $env:UPDATE_TEST_URL = $(if ($url) { $url } else { "https://github.com/smholte/CAD-render-animation/releases/latest/download/index.json" })
            $env:FRESING_UPDATE_RESTART = ConvertTo-Json -Compress @($exe.FullName, "--background", "--python-exit-code", "1",
                                                                     "--python", $script, "--", "after", $after)
            Note "The old app looks for an update, presses Update now and closes"
            $t0 = Get-Date
            $log = Join-Path $OutDir "update_before_blender.log"
            $p = Start-Process -FilePath $exe.FullName -ArgumentList @("--background", "--python-exit-code", "1", "--python",
                    "`"$script`"", "--", "before", "`"$before`"") -NoNewWindow -PassThru `
                    -RedirectStandardOutput $log -RedirectStandardError (Join-Path $OutDir "update_before_blender.stderr.log")
            $null = $p.Handle
            if (-not $p.WaitForExit(10 * 60 * 1000)) {
                & taskkill /T /F /PID $p.Id | Out-Null
                Problem "the old app did not close within 10 minutes"
            }
            Get-Content -LiteralPath $log | ForEach-Object { Write-Host "   $_" }
            Note "Waiting for update_helper.py to install and start the app again"
            $deadline = (Get-Date).AddMinutes(10)
            while (-not (Test-Path -LiteralPath $after) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
            $secs = [math]::Round(((Get-Date) - $t0).TotalSeconds)
            # the app started again (and the helper) must be gone before Install.bat runs over it
            $gone = (Get-Date).AddSeconds(90)
            do {
                $left = Get-Process -Name blender, blender-launcher, python -ErrorAction SilentlyContinue |
                    Where-Object { $_.Path -and $_.Path.StartsWith("$InstallDir\", [StringComparison]::OrdinalIgnoreCase) }
                if ($left) { Start-Sleep -Seconds 1 }
            } while ($left -and (Get-Date) -lt $gone)
            if ($left) { Problem "still running 90 s after the update: $($left.Path -join ', ')" }
            foreach ($f in @($before, $after)) {
                $label = if ($f -eq $before) { "old app" } else { "after the update" }
                if (-not (Test-Path -LiteralPath $f)) { Problem "$label wrote no results ($(Split-Path -Leaf $f))"; continue }
                $res = Get-Content -LiteralPath $f -Raw -Encoding utf8 | ConvertFrom-Json
                foreach ($c in $res.checks) {
                    $Summary += "| Update, $($label): $($c[0]) | $(if ($c[1]) { '✅' } else { '❌ ' + $c[2] }) | |"
                    if (-not $c[1]) { Problem "update, $($label): $($c[0]) - $($c[2])" }
                }
            }
            $updLog = Join-Path $portable "config\fresing_update\update.log"
            $logText = if (Test-Path -LiteralPath $updLog) { Get-Content -LiteralPath $updLog -Raw -Encoding utf8 } else { "" }
            if (Test-Path -LiteralPath $updLog) { Copy-Item -LiteralPath $updLog -Destination (Join-Path $OutDir "update.log") }
            Write-Host "----- update.log -----"; Write-Host $logText
            $manifest = Join-Path $portable "extensions\user_default\fresing_render\blender_manifest.toml"
            $ver = ""
            if (Test-Path -LiteralPath $manifest) {
                $ver = [regex]::Match((Get-Content -LiteralPath $manifest -Raw), '(?m)^version\s*=\s*"([^"]+)"').Groups[1].Value
            }
            $tmpl = Join-Path $portable "scripts\startup\bl_app_templates_user\fresing_render\__init__.py"
            $shipped = Join-Path $portable "extensions\user_default\fresing_render\app_template_files\__init__.py"
            $sameTemplate = (Test-Path -LiteralPath $tmpl) -and (Test-Path -LiteralPath $shipped) -and
                ((Get-FileHash -LiteralPath $tmpl).Hash -eq (Get-FileHash -LiteralPath $shipped).Hash)
            $guideLnk = Join-Path $Programs "Fresing Render\Fresing Render - User guide.lnk"
            $guideOk = $false
            if (Test-Path -LiteralPath $guideLnk) {
                $guideOk = Test-Path -LiteralPath ((New-Object -ComObject WScript.Shell).CreateShortcut($guideLnk).TargetPath)
            }
            $files = [ordered]@{
                "Update: extension $Expect installed (found '$ver')" = ($ver -eq $Expect)
                "Update: app template = the one in the new extension" = $sameTemplate
                "Update: log says installed and started again" = ($logText -match "OK: Updated to" -and $logText -match "started again:")
                "Update: user guide shortcut still opens the guide" = $guideOk
            }
            foreach ($k in $files.Keys) {
                if (-not $files[$k]) { Problem $k }
                $Summary += "| $k | $(if ($files[$k]) { '✅' } else { '❌' }) | |"
            }
            $Summary += "| Update: old app start -> new app checked | | $secs s |"
            foreach ($v in "UPDATE_TEST_EXPECT", "UPDATE_TEST_OLD", "UPDATE_TEST_URL", "UPDATE_TEST_PROJECT", "FRESING_UPDATE_RESTART") {
                Remove-Item "Env:$v" -ErrorAction SilentlyContinue
            }
        } elseif ($ok) {
            Problem "no blender.exe after installing the old version"
        }
    }
    if (-not $OnlyUpdate) {
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
            "PC check shortcuts"       = (Test-Path -LiteralPath (Join-Path $Programs "Fresing Render\Fresing Render - PC check (quick).lnk")) -and
                                         (Test-Path -LiteralPath (Join-Path $Programs "Fresing Render\Fresing Render - PC check (full).lnk"))
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

        # ---- 5. the PC check (Full), started exactly like its Start-menu shortcut (task 0032) ----------
        $pcLnk = Join-Path $Programs "Fresing Render\Fresing Render - PC check (full).lnk"
        if ($BlenderExe -and (Test-Path -LiteralPath $pcLnk)) {
            $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut($pcLnk)
            Note "PC check: `"$($lnk.TargetPath)`" $($lnk.Arguments)"
            $report = Join-Path $Desktop "Fresing Render PC check.html"
            Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue
            $log = Join-Path $OutDir "pccheck_blender.log"
            $t0 = Get-Date
            $p = Start-Process -FilePath $lnk.TargetPath -ArgumentList $lnk.Arguments -WorkingDirectory $lnk.WorkingDirectory `
                -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError (Join-Path $OutDir "pccheck_blender.stderr.log")
            $null = $p.Handle
            if (-not $p.WaitForExit($PcCheckMinutes * 60 * 1000)) {
                & taskkill /T /F /PID $p.Id | Out-Null
                Problem "the PC check did not finish within $PcCheckMinutes minutes"
            }
            $secs = [math]::Round(((Get-Date) - $t0).TotalSeconds)
            Write-Host "----- PC check output -----"
            Get-Content -LiteralPath $log | ForEach-Object { Write-Host "   $_" }
            if (Test-Path -LiteralPath $report) {
                Copy-Item -LiteralPath $report -Destination (Join-Path $OutDir "Fresing Render PC check.html")
            } else {
                Problem "the PC check wrote no report on the Desktop"
            }
            $hist = Join-Path $BlenderExe.DirectoryName "portable\config\fresing_pccheck"
            $block = Join-Path $hist "last_run.txt"
            if (Test-Path -LiteralPath $block) {
                Copy-Item -LiteralPath $block -Destination (Join-Path $OutDir "pccheck_last_run.txt")
            } else {
                Problem "the PC check left no numbers in $hist"
            }
            $Summary += "| PC check, Full (Start-menu shortcut) | finished, judged below | $secs s |"
        }
    }
}

$table = @("### Windows install ($(if ($Uninstall) { 'uninstall' } else { 'install' })): $(if ($Problems) { 'FAILED' } else { 'passed' })", "",
           "| Step | Result | Time |", "| --- | --- | --- |") + $Summary
if ($Problems) { $table += @("", "**Problems:**", "") + ($Problems | ForEach-Object { "- $_" }) }
$text = ($table -join "`n") + "`n"
Write-Host $text
if ($env:GITHUB_STEP_SUMMARY) { Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Value $text -Encoding utf8 }
if ($Problems) { exit 1 }
