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
  5. Starts the self-test exactly as its shortcut "Self test" in the app's Tools folder does (task 0212)
     and copies its report to -OutDir. The report is judged afterwards by tools/ci_check_selftest.py.
  6. Starts the PC check (Full) exactly as its Tools-folder shortcut does and copies its report and its
     text block (pccheck_last_run.txt) to -OutDir; judged afterwards by tools/ci_check_pccheck.py.
  With -Uninstall it instead runs Uninstall.bat and checks that everything is gone.

  -Part (task 0171: GitHub runs two parts at once, each on its own Windows machine):
    all  everything below (the default; the owner's or a chat's own run)
    a    the in-app update, Install.bat twice, files, icons, Fresing Render.exe, self-test, PC check Full
    b    Install.bat once, files, PC check Heavy (scaled down)

  In-app update (task 0020), before step 2 when -OldReleaseZip is given:
  U1. Install.bat of an old build (the same code as version 0.0.1 with the app template of 0.2.10),
      fresh, with -UpdateUrl pointing at -UpdateRepo (a local copy of the update listing, in a folder with
      a space and an accent) - or, with -UpdateFrom github, at the real newest release on GitHub.
  U2. The old app (in the background) runs tools/update_test_blender.py: it must find -Expect, press
      Update now and close; update_helper.py installs the update and starts the app again with "-- after",
      which checks the new version, the message and the app template.
  U3. Checks the files: installed version, app template = the new one, update log, the user-guide shortcut, and
      (task 0212) that the old build's extra shortcuts - put back as an install before 0212 had them - were tidied
      away by what the app runs at start: only "Fresing Render" on the Desktop and in the Start menu.
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
    [switch]$OnlyUpdate,
    [string]$PcCheckOnly = "",       # run only these lines of the PC check (Full): comma-separated ids (task 0063)
    [ValidateSet("all", "a", "b")] [string]$Part = "all"   # task 0171: which part of the test (see above)
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

# Task 0212: only "Fresing Render" on the Desktop and in the Start menu (directly in Programs); the extras in the
# Tools folder of the install folder.
$ToolsDir = Join-Path $InstallDir "Tools"
$ToolNames = @("Self test.lnk", "PC check (quick).lnk", "PC check (full).lnk", "PC check (heavy).lnk", "Safe start.lnk", "User guide.lnk")
$OldMenu = Join-Path $Programs "Fresing Render"
function Check-OneShortcut([string]$when) {
    $desk = @(Get-ChildItem -LiteralPath $Desktop -Filter "Fresing Render*.lnk" -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
    $menu = @(Get-ChildItem -LiteralPath $Programs -Filter "Fresing Render*" -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
    $tools = @(Get-ChildItem -LiteralPath $ToolsDir -Filter "*.lnk" -ErrorAction SilentlyContinue | ForEach-Object { $_.Name } | Sort-Object)
    $bad = @()
    if (($desk -join "|") -ne "Fresing Render.lnk") { $bad += "Desktop: $($desk -join ', ')" }
    if (($menu -join "|") -ne "Fresing Render.lnk") { $bad += "Start menu: $($menu -join ', ')" }
    if (($tools -join "|") -ne (($ToolNames | Sort-Object) -join "|")) { $bad += "Tools folder: $($tools -join ', ')" }
    Write-Host "   ($when) Desktop: $($desk -join ', ') / Start menu: $($menu -join ', ') / Tools: $($tools -join ', ')"
    if ($bad) { Problem "one shortcut only ($when): $($bad -join '; ')" }
    $script:Summary += "| Only Fresing Render on the Desktop and in the Start menu, 6 in the Tools folder ($when) | $(if (-not $bad) { '✅' } else { '❌ ' + ($bad -join '; ') }) | |"
}
# An install before 0212: the extras in a Start-menu folder "Fresing Render" (with the app's own shortcut) and two
# PC-check shortcuts on the Desktop; made from the current ones (same targets), the Tools folder taken away.
# -Foreign: also a shortcut with an old name that points elsewhere (it must be left alone).
function Make-OldLayout([switch]$Foreign) {
    $sh = New-Object -ComObject WScript.Shell
    New-Item -ItemType Directory -Force -Path $OldMenu | Out-Null
    $app = Join-Path $Programs "Fresing Render.lnk"
    if (Test-Path -LiteralPath $app) { Move-Item -LiteralPath $app -Destination (Join-Path $OldMenu "Fresing Render.lnk") -Force }
    $map = [ordered]@{ "Self test.lnk" = "Fresing Render - Self test.lnk"; "PC check (quick).lnk" = "Fresing Render - PC check (quick).lnk"
                       "PC check (full).lnk" = "Fresing Render - PC check (full).lnk"; "PC check (heavy).lnk" = "Fresing Render - PC check (heavy).lnk"
                       "Safe start.lnk" = "Fresing Render - safe start.lnk"; "User guide.lnk" = "Fresing Render - User guide.lnk" }
    foreach ($k in $map.Keys) {
        $src = Join-Path $ToolsDir $k
        if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $OldMenu $map[$k]) -Force }
    }
    foreach ($pair in @(@("PC check (quick).lnk", "Fresing Render - PC check.lnk"), @("PC check (heavy).lnk", "Fresing Render - PC check (heavy).lnk"))) {
        $src = Join-Path $ToolsDir $pair[0]
        if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $Desktop $pair[1]) -Force }
    }
    if ($Foreign) {
        Remove-Item -LiteralPath (Join-Path $Desktop "Fresing Render - PC check (heavy).lnk") -Force -ErrorAction SilentlyContinue
        $l = $sh.CreateShortcut((Join-Path $Desktop "Fresing Render - PC check (heavy).lnk"))
        $l.TargetPath = Join-Path $env:WINDIR "notepad.exe"; $l.Save()
    }
    Remove-Item -LiteralPath $ToolsDir -Recurse -Force -ErrorAction SilentlyContinue
    $n = @(Get-ChildItem -LiteralPath $OldMenu -Filter "*.lnk").Count
    Note "An older install's shortcuts put back: $n in the Start-menu folder, 2 on the Desktop$(if ($Foreign) { ' (one of them someone else''s)' })"
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
# task 0217: the installer writes the Toolbox folder into the user's home folder (the runner's own: changing USERPROFILE
# for the whole test makes Windows answer "" for the Desktop folder and the installer stops); the inbox checks run with
# a user folder with a space and an accent (ci_toolbox_windows.py)
$ToolboxHome = Join-Path $env:USERPROFILE "Toolbox"
$FakeProfile = Join-Path $WorkDir "Users\Sébastien Test"
Remove-Item Env:TOOLBOX_HOME -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $FakeProfile | Out-Null
$env:FRESING_NO_WELCOME = "1"          # task 0199: no welcome / What's new window in the tests
New-Item -ItemType Directory -Force -Path $LocalAppData | Out-Null

# Task 0144: the render kit's window script runs in Windows PowerShell 5.1 (the kit's .bat starts powershell.exe):
# it must parse there, and its expected-time loop must give the numbers of kit_run.wall_seconds (tests/test_kit_window.py).
$KitWindow = Join-Path $PSScriptRoot "..\site\render_kit\kit_window.ps1"
$KitLayoutRuns = @("1.0 1920x1080", "1.25 1920x1080", "1.5 1366x768", "1.5 1920x1080", "1.75 1920x1080", "2.0 1920x1080")
if (-not $Uninstall -and $Part -ne "b" -and (Test-Path -LiteralPath $KitWindow)) {
    Note "Render kit window: parse and expected time in Windows PowerShell 5.1"
    $probe = Join-Path $WorkDir "kit_window_probe.ps1"
    $kitPath = (Resolve-Path -LiteralPath $KitWindow).Path
    Set-Content -LiteralPath $probe -Encoding utf8BOM -Value @"
`$errs = `$null
[void][System.Management.Automation.Language.Parser]::ParseFile('$kitPath', [ref]`$null, [ref]`$errs)
if (`$errs.Count) { `$errs | ForEach-Object { 'PARSE line ' + `$_.Extent.StartLineNumber + ': ' + `$_.Message }; exit 5 }
. '$kitPath' -Mode lib
'WALL ' + [math]::Round((Get-WallSeconds 3600 600 ([datetime]'2026-11-15T12:00:00') 70 `$false '22:00' '07:00' 60), 0)
'WALL ' + [math]::Round((Get-WallSeconds 14400 0 ([datetime]'2026-11-15T20:00:00') 100 `$true '22:00' '07:00' 50), 0)
'PS ' + `$PSVersionTable.PSVersion.Major
"@
    $savedModulePath = $env:PSModulePath
    Remove-Item Env:PSModulePath -ErrorAction SilentlyContinue
    try {
        $said = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $probe 2>&1 | ForEach-Object { "$_" }
        $code = $LASTEXITCODE
    } finally {
        $env:PSModulePath = $savedModulePath
    }
    $said | ForEach-Object { Write-Host "   $_" }
    $want = @("WALL 5743", "WALL 21600", "PS 5")
    if ($code -ne 0 -or ($want | Where-Object { $said -notcontains $_ })) {
        Problem "the render kit's kit_window.ps1 does not parse or compute in Windows PowerShell 5.1 (exit $code): $($said -join ' / ')"
    }

    # Task 0177: the kit's windows at 100-200 % display scale (fonts and distances as at that scale; the start window must
    # also fit a 1366 x 768 screen at 150 %): every text fits, nothing overlaps; a picture of each in <OutDir>\kit_window.
    Note "Render kit windows: layout at 100-200 % display scale"
    $layout = Join-Path $PSScriptRoot "ci_kit_window_layout.ps1"
    $shots = Join-Path $OutDir "kit_window"
    foreach ($run in $KitLayoutRuns) {
        $scale, $screen = $run.Split(" ")
        Remove-Item Env:PSModulePath -ErrorAction SilentlyContinue
        try {
            $said = & powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File $layout -Scale $scale -Screen $screen -OutDir $shots 2>&1 |
                ForEach-Object { "$_" }
            $code = $LASTEXITCODE
        } finally {
            $env:PSModulePath = $savedModulePath
        }
        $said | ForEach-Object { Write-Host "   $_" }
        if ($code -ne 0) {
            $bad = @($said | Where-Object { $_ -like "LAYOUT PROBLEM*" -or $_ -like "*Exception*" -or $_ -like "*error*" }) | Select-Object -First 6
            Problem "the render kit's windows do not fit at $run (exit $code): $($bad -join ' / ')"
        }
    }
}

if ($Uninstall) {
    $bat = Get-ChildItem -LiteralPath $UnzipDir -Recurse -Filter "Uninstall.bat" | Select-Object -First 1
    if (-not $bat) { throw "Uninstall.bat not found under $UnzipDir (run the install part first)" }
    Note "Uninstall.bat"
    $r = Run-Bat $bat.FullName "uninstall" 5
    if (Test-Path -LiteralPath $InstallDir) { Problem "Uninstall left $InstallDir behind" }
    if (Test-Path -LiteralPath (Join-Path $Desktop "Fresing Render.lnk")) { Problem "Uninstall left the Desktop shortcut" }
    if (Test-Path -LiteralPath (Join-Path $Programs "Fresing Render.lnk")) { Problem "Uninstall left the Start-menu shortcut" }
    if (Test-Path -LiteralPath $OldMenu) { Problem "Uninstall left the Start-menu folder" }
    $leftLinks = @(Get-ChildItem -LiteralPath $Desktop -Filter "Fresing Render*.lnk" -ErrorAction SilentlyContinue)
    if ($leftLinks) { Problem "Uninstall left on the Desktop: $($leftLinks.Name -join ', ')" }
    if ($r.Text -notmatch "Fresing Render removed") { Problem "Uninstall did not say 'Fresing Render removed'" }
    # task 0217: only the app's own folder of the Toolbox folder goes
    if (Test-Path -LiteralPath (Join-Path $ToolboxHome "tools\nl.fresing.render")) { Problem "Uninstall left tools\nl.fresing.render in the Toolbox folder" }
    if (-not (Test-Path -LiteralPath (Join-Path $ToolboxHome "toolbox-folder.json"))) { Problem "Uninstall removed the Toolbox folder itself" }
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
        if ($ok) { Make-OldLayout }       # task 0212: the old build as an install before 0212 left it
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
                $left = Get-Process -Name blender, blender-launcher, "Fresing Render", python -ErrorAction SilentlyContinue |
                    Where-Object { $procPath = $_.Path; $procPath -and $procPath.StartsWith("$InstallDir\", [StringComparison]::OrdinalIgnoreCase) }
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
            $guideLnk = Join-Path $ToolsDir "User guide.lnk"
            $guideOk = $false
            if (Test-Path -LiteralPath $guideLnk) {
                $guideOk = Test-Path -LiteralPath ((New-Object -ComObject WScript.Shell).CreateShortcut($guideLnk).TargetPath)
            }
            $files = [ordered]@{
                "Update: extension $Expect installed (found '$ver')" = ($ver -eq $Expect)
                "Update: app template = the one in the new extension" = $sameTemplate
                "Update: log says installed and started again" = ($logText -match "OK: Updated to" -and $logText -match "started again:")
                "Update: user guide shortcut still opens the guide" = $guideOk
                "Update: licence files arrived inside the extension" = (Test-Path -LiteralPath (Join-Path $portable "extensions\user_default\fresing_render\licenses\LICENSE"))
            }
            foreach ($k in $files.Keys) {
                if (-not $files[$k]) { Problem $k }
                $Summary += "| $k | $(if ($files[$k]) { '✅' } else { '❌' }) | |"
            }
            $Summary += "| Update: old app start -> new app checked | | $secs s |"
            Check-OneShortcut "after the old build updated itself in the app"
            foreach ($v in "UPDATE_TEST_EXPECT", "UPDATE_TEST_OLD", "UPDATE_TEST_URL", "UPDATE_TEST_PROJECT", "FRESING_UPDATE_RESTART") {
                Remove-Item "Env:$v" -ErrorAction SilentlyContinue
            }
        } elseif ($ok) {
            Problem "no blender.exe after installing the old version"
        }
    }
    if (-not $OnlyUpdate) {
        # ---- 2. install twice: fresh, then repair over it ----------------------------------
        foreach ($round in $(if ($Part -eq "b") { @("install") } else { @("install", "repair") })) {
            # task 0212: the repair runs over an older install's shortcuts, one of them someone else's
            if ($round -eq "repair") { Make-OldLayout -Foreign }
            Note "Install.bat ($round)"
            $r = Run-Bat $bat.FullName $round
            $done = $r.Text -match "Done\. Start 'Fresing Render' from the Desktop\."
            $ok = $done -and ($r.Code -eq 0)
            if (-not $done) { Problem "Install.bat ($round) did not reach 'Done.' - see $round.log" }
            if ($r.Code -ne 0) { Problem "Install.bat ($round) ended with exit code $($r.Code)" }
            $Summary += "| Install.bat ($round) | $(if ($ok) { '✅' } else { '❌' }) exit code $($r.Code) | $($r.Seconds) s |"
            if (-not $ok) { break }
            if ($round -eq "repair") {
                $foreign = Join-Path $Desktop "Fresing Render - PC check (heavy).lnk"
                $kept = (Test-Path -LiteralPath $foreign) -and ((New-Object -ComObject WScript.Shell).CreateShortcut($foreign).TargetPath -like "*notepad.exe")
                if (-not $kept) { Problem "Install.bat (repair) removed a shortcut that points elsewhere (someone else's)" }
                $Summary += "| Install.bat (repair): an old-named shortcut that points elsewhere is left alone | $(if ($kept) { '✅' } else { '❌' }) | |"
                Remove-Item -LiteralPath $foreign -Force -ErrorAction SilentlyContinue
            }
            Check-OneShortcut "after Install.bat ($round)"
        }

        # ---- 3. what the installer must leave behind ------------------------------------
        $BlenderExe = Get-ChildItem -LiteralPath $InstallDir -Recurse -Filter "blender.exe" -Depth 1 -ErrorAction SilentlyContinue | Select-Object -First 1
        $checks = [ordered]@{
            "Blender program"          = [bool]$BlenderExe
            "installed.txt"            = Test-Path -LiteralPath (Join-Path $InstallDir "installed.txt")
            "Desktop shortcut"         = Test-Path -LiteralPath (Join-Path $Desktop "Fresing Render.lnk")
            "Start-menu shortcut"      = Test-Path -LiteralPath (Join-Path $Programs "Fresing Render.lnk")
            "Self-test shortcut (Tools folder)" = Test-Path -LiteralPath (Join-Path $ToolsDir "Self test.lnk")
            "PC check shortcuts (Tools folder)" = (Test-Path -LiteralPath (Join-Path $ToolsDir "PC check (quick).lnk")) -and
                                         (Test-Path -LiteralPath (Join-Path $ToolsDir "PC check (full).lnk")) -and
                                         (Test-Path -LiteralPath (Join-Path $ToolsDir "PC check (heavy).lnk"))
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
            # task 0206: the licence files, Blender's own licence folder, Blender's extension sync off
            $licDir = Join-Path $InstallDir "licenses"
            $checks["Licence files next to the app"] = (Test-Path -LiteralPath (Join-Path $licDir "LICENSE")) -and
                (Test-Path -LiteralPath (Join-Path $licDir "THIRD-PARTY-NOTICES.md")) -and
                (Test-Path -LiteralPath (Join-Path $licDir "third-party\SOURCES.txt"))
            $inExt = Join-Path $portable "extensions\user_default\fresing_render\licenses"
            $checks["Licence files inside the extension"] = (Test-Path -LiteralPath (Join-Path $inExt "LICENSE")) -and
                (Test-Path -LiteralPath (Join-Path $inExt "THIRD-PARTY-NOTICES.md")) -and
                (Test-Path -LiteralPath (Join-Path $inExt "third-party\SOURCES.txt"))
            $checks["Blender's own license folder"] = [bool](Get-ChildItem -LiteralPath (Join-Path $BlenderExe.DirectoryName "license") -ErrorAction SilentlyContinue | Select-Object -First 1)
            $syncProbe = "import bpy, sys; on = [r.name for r in bpy.context.preferences.extensions.repos if r.use_remote_url and r.use_sync_on_startup]; print('SYNC-ON-START:', on); sys.exit(1 if on else 0)"
            $oldEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
            & $BlenderExe.FullName --background --python-expr $syncProbe 2>&1 | ForEach-Object { Write-Host "   $_" }
            $syncCode = $LASTEXITCODE
            $ErrorActionPreference = $oldEap
            $checks["Blender's extension sync off at start (exit code $syncCode)"] = ($syncCode -eq 0)
            # task 0217: the Toolbox folder and the app's manifest, and what only Windows shows (tools/ci_toolbox_windows.py)
            $checks["Toolbox folder and manifest under %USERPROFILE%"] = (Test-Path -LiteralPath (Join-Path $ToolboxHome "toolbox-folder.json")) -and
                (Test-Path -LiteralPath (Join-Path $ToolboxHome "tools\nl.fresing.render\toolbox.json"))
            if ($Part -ne "b") {                  # (part A only: these checks run once, after the install and repair)
                $tbScript = Join-Path $PSScriptRoot "ci_toolbox_windows.py"
                $oldEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
                $realProfile = $env:USERPROFILE
                $env:USERPROFILE = $FakeProfile          # only for this one Blender: Python's home folder
                try {
                    & $BlenderExe.FullName --background --python-exit-code 1 --python $tbScript -- (Join-Path $FakeProfile "Toolbox") 2>&1 | ForEach-Object { Write-Host "   $_" }
                    $tbCode = $LASTEXITCODE
                } finally { $env:USERPROFILE = $realProfile }
                $ErrorActionPreference = $oldEap
                $checks["Toolbox inbox on Windows: short file, open status.json, junction (exit code $tbCode)"] = ($tbCode -eq 0)
            }
        }
        foreach ($k in $checks.Keys) {
            if (-not $checks[$k]) { Problem "missing after install: $k" }
            $Summary += "| $k | $(if ($checks[$k]) { '✅' } else { '❌' }) | |"
        }

        if ($Part -ne "b") {             # part b: only what the PC check Heavy needs
        # ---- 3b. the Fresing icon (task 0169) ------------------------------------------------
        $IconFile = Join-Path $InstallDir "fresing-render.ico"
        $sh = New-Object -ComObject WScript.Shell
        $shellApp = New-Object -ComObject Shell.Application
        function Read-Lnk([string]$path) {
            $l = $sh.CreateShortcut($path)
            $id = ""
            try { $id = "" + $shellApp.NameSpace((Split-Path -Parent $path)).ParseName((Split-Path -Leaf $path)).ExtendedProperty("System.AppUserModel.ID") } catch { }
            return @{ Icon = $l.IconLocation; Target = $l.TargetPath; Args = $l.Arguments; Id = $id }
        }
        function Our-Links() {
            @(Get-ChildItem -LiteralPath $Desktop -Filter "Fresing Render*.lnk" -ErrorAction SilentlyContinue) +
            @(Get-ChildItem -LiteralPath $Programs -Filter "Fresing Render.lnk" -ErrorAction SilentlyContinue) +
            @(Get-ChildItem -LiteralPath $ToolsDir -Filter "*.lnk" -ErrorAction SilentlyContinue)
        }
        function Check-Links([string]$when) {
            $links = Our-Links
            $bad = @()
            foreach ($f in $links) {
                $r = Read-Lnk $f.FullName
                $iconOk = ($r.Icon -ieq "$IconFile,0") -and ($r.Icon -notmatch 'blender(-launcher)?\.exe')
                if (-not $iconOk) { $bad += "$($f.Name): icon '$($r.Icon)'" }
                if ($r.Args -match '--app-template fresing_render' -and $r.Id -ne "Fresing.Render") { $bad += "$($f.Name): app ID '$($r.Id)'" }
                # task 0177: the app's shortcuts start "Fresing Render.exe" (the console ones stay on blender.exe)
                $wantExe = $(if ($f.Name -eq "Safe start.lnk") { Join-Path $BlenderExe.DirectoryName "blender-launcher.exe" } else { $AppExe })
                if ($r.Args -match '--app-template fresing_render' -and $AppExe -and $r.Target -ine $wantExe) { $bad += "$($f.Name): starts '$($r.Target)'" }
                Write-Host "   $($f.Name): icon '$($r.Icon)', app ID '$($r.Id)', starts '$(Split-Path -Leaf $r.Target)'"
            }
            $ok = ($links.Count -ge 8) -and (-not $bad) -and (Test-Path -LiteralPath $IconFile)
            if (-not $ok) { Problem "icon ($when): $($links.Count) shortcuts, icon file $(Test-Path -LiteralPath $IconFile); $($bad -join '; ')" }
            $script:Summary += "| Fresing icon + app ID on every shortcut ($when, $($links.Count)) | $(if ($ok) { '✅' } else { '❌ ' + ($bad -join '; ') }) | |"
        }
        # ---- 3c. "Fresing Render.exe" (task 0177): Task Manager's name, no console, Defender, no Mark of the Web -------
        $AppExe = ""
        if ($BlenderExe) {
            $AppExe = Join-Path $BlenderExe.DirectoryName "Fresing Render.exe"
            $exeOk = Test-Path -LiteralPath $AppExe
            $Summary += "| Fresing Render.exe made by Install.bat | $(if ($exeOk) { '✅' } else { '❌' }) | |"
            if (-not $exeOk) { Problem "Install.bat made no Fresing Render.exe"; $AppExe = "" }
        }
        if ($AppExe) {
            $fileDesc = (Get-Item -LiteralPath $AppExe).VersionInfo.FileDescription
            $zone = Get-Item -LiteralPath $AppExe -Stream Zone.Identifier -ErrorAction SilentlyContinue
            # the running process, as Task Manager reads it (a background run that waits a little)
            $p = Start-Process -FilePath $AppExe -ArgumentList @("--background", "--factory-startup", "--python-expr",
                    "`"import time; time.sleep(25)`"") -WorkingDirectory $BlenderExe.DirectoryName -PassThru -WindowStyle Hidden
            $runDesc = ""; $runProduct = ""
            for ($i = 0; $i -lt 20 -and -not $runDesc; $i++) {
                Start-Sleep -Seconds 1
                try { $gp = Get-Process -Id $p.Id -ErrorAction Stop; $runDesc = $gp.Description; $runProduct = $gp.Product } catch { }
            }
            $running = [bool](Get-Process -Id $p.Id -ErrorAction SilentlyContinue)
            if ($running) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
            Write-Host "   Fresing Render.exe: file '$fileDesc', running process '$runDesc' / '$runProduct'"
            $rows = [ordered]@{
                "Fresing Render.exe: FileDescription of the file = Fresing Render ('$fileDesc')" = ($fileDesc -eq "Fresing Render")
                "Fresing Render.exe: the running process is called Fresing Render ('$runDesc')" = ($runDesc -eq "Fresing Render" -and $runProduct -eq "Fresing Render")
                "Fresing Render.exe: kept running until stopped (not blocked)" = $running
                "Fresing Render.exe: no Mark of the Web (SmartScreen does not check it)" = (-not $zone)
            }
            # Windows Defender: scan the copy (exit code 0 = nothing found, 2 = a threat)
            $mpcmd = Join-Path $env:ProgramFiles "Windows Defender\MpCmdRun.exe"
            if (Test-Path -LiteralPath $mpcmd) {
                $scan = & $mpcmd -Scan -ScanType 3 -File $AppExe -DisableRemediation 2>&1 | ForEach-Object { "$_" }
                $scanCode = $LASTEXITCODE
                $scan | Select-Object -Last 6 | ForEach-Object { Write-Host "   (Defender) $_" }
                $rows["Fresing Render.exe: Windows Defender scan finds nothing (exit code $scanCode)"] = ($scanCode -eq 0)
            } else {
                $Summary += "| Fresing Render.exe: Windows Defender scan | skipped: no Defender on this machine | |"
            }
            foreach ($k in $rows.Keys) {
                if (-not $rows[$k]) { Problem $k }
                $Summary += "| $k | $(if ($rows[$k]) { '✅' } else { '❌' }) | |"
            }
        }

        Note "Fresing icon on the shortcuts (Install.bat)"
        Check-Links "after Install.bat"

        # an install from before 0169 / 0177: Blender's icon, no app ID, no icon file, the app shortcut on Blender's
        # launcher and no Fresing Render.exe; the app's start-up refresh fixes it
        if ($BlenderExe) {
            Note "An older install's shortcuts: refreshed by the app's code (tools/appicon_test.py)"
            $launcher = Join-Path $BlenderExe.DirectoryName "blender-launcher.exe"
            foreach ($old in @((Join-Path $Desktop "Fresing Render.lnk"), (Join-Path $ToolsDir "Self test.lnk"))) {
                $r = Read-Lnk $old
                Remove-Item -LiteralPath $old -Force
                $l = $sh.CreateShortcut($old)
                $l.TargetPath = $(if ($r.Args -match 'app-template') { $launcher } else { $r.Target })
                $l.Arguments = $r.Args; $l.WorkingDirectory = $BlenderExe.DirectoryName
                $l.IconLocation = "$($BlenderExe.FullName),0"; $l.Save()
            }
            Remove-Item -LiteralPath $IconFile -Force -ErrorAction SilentlyContinue
            foreach ($f in @("Fresing Render.exe", "fresing-render-exe.json")) {
                Remove-Item -LiteralPath (Join-Path $BlenderExe.DirectoryName $f) -Force -ErrorAction SilentlyContinue
            }
            Remove-Item -LiteralPath (Join-Path $ToolsDir "Safe start.lnk") -Force -ErrorAction SilentlyContinue
            $res = Join-Path $OutDir "appicon_test.json"
            $script = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "tools\appicon_test.py"
            $log = Join-Path $OutDir "appicon_test.log"
            $t0 = Get-Date
            $p = Start-Process -FilePath $BlenderExe.FullName -ArgumentList @("--background", "--python-exit-code", "1", "--python",
                    "`"$script`"", "--", "`"$res`"") -NoNewWindow -PassThru -RedirectStandardOutput $log `
                    -RedirectStandardError (Join-Path $OutDir "appicon_test.stderr.log")
            $null = $p.Handle
            if (-not $p.WaitForExit(5 * 60 * 1000)) { & taskkill /T /F /PID $p.Id | Out-Null; Problem "appicon_test.py did not finish in 5 minutes" }
            Get-Content -LiteralPath $log | ForEach-Object { Write-Host "   $_" }
            if (-not (Test-Path -LiteralPath $res)) { Problem "appicon_test.py wrote no results" }
            else {
                foreach ($c in (Get-Content -LiteralPath $res -Raw -Encoding utf8 | ConvertFrom-Json).checks) {
                    $Summary += "| Icon: $($c[0]) | $(if ($c[1]) { '✅' } else { '❌ ' + $c[2] }) | |"
                    if (-not $c[1]) { Problem "icon: $($c[0]) - $($c[2])" }
                }
            }
            $Summary += "| Icon: older install refreshed + window checks | | $([math]::Round(((Get-Date) - $t0).TotalSeconds)) s |"
            Check-Links "older install after the app's refresh"
            Check-OneShortcut "after the app's refresh of an older install"
        }
        }

        # ---- 4. the self-test, started exactly like its shortcut in the Tools folder (task 0212) ---------
        $lnkPath = Join-Path $ToolsDir "Self test.lnk"
        if ($Part -ne "b" -and -not (Test-Path -LiteralPath $lnkPath)) { Problem "no self-test shortcut in the Tools folder" }
        if ($Part -ne "b" -and (Test-Path -LiteralPath $lnkPath)) {
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
            $Summary += "| Self-test (Tools-folder shortcut) | finished, judged below | $secs s |"
        }

        # ---- 6. the PC check (Full), then Heavy scaled down (task 0033), each started exactly like its
        #         shortcut in the Tools folder (task 0212) ----------------------------------------------
        $pcModes = switch ($Part) { "a" { @("full") } "b" { @("heavy") } default { @("full", "heavy") } }
        foreach ($pcMode in $pcModes) {
        $pcLnk = Join-Path $ToolsDir "PC check ($pcMode).lnk"
        if ($BlenderExe -and -not (Test-Path -LiteralPath $pcLnk)) { Problem "no PC check ($pcMode) shortcut in the Tools folder" }
        $pcTag = if ($pcMode -eq "heavy") { "pccheck_heavy" } else { "pccheck" }
        $env:FRESING_PCCHECK_HEAVY_SMALL = if ($pcMode -eq "heavy") { "1" } else { "" }
        $env:FRESING_PCCHECK_ONLY = if ($pcMode -eq "full") { $PcCheckOnly } else { "" }
        if ($BlenderExe -and (Test-Path -LiteralPath $pcLnk)) {
            $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut($pcLnk)
            Note "PC check: `"$($lnk.TargetPath)`" $($lnk.Arguments)"
            $report = Join-Path $Desktop "Fresing Render PC check.html"
            Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue
            $log = Join-Path $OutDir "$pcTag`_blender.log"
            $t0 = Get-Date
            $p = Start-Process -FilePath $lnk.TargetPath -ArgumentList $lnk.Arguments -WorkingDirectory $lnk.WorkingDirectory `
                -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError (Join-Path $OutDir "$pcTag`_blender.stderr.log")
            $null = $p.Handle
            if (-not $p.WaitForExit($PcCheckMinutes * 60 * 1000)) {
                & taskkill /T /F /PID $p.Id | Out-Null
                Problem "the PC check did not finish within $PcCheckMinutes minutes"
            }
            $secs = [math]::Round(((Get-Date) - $t0).TotalSeconds)
            Write-Host "----- PC check output -----"
            Get-Content -LiteralPath $log | ForEach-Object { Write-Host "   $_" }
            if (Test-Path -LiteralPath $report) {
                Copy-Item -LiteralPath $report -Destination (Join-Path $OutDir "$pcTag`.html")
            } else {
                Problem "the PC check wrote no report on the Desktop"
            }
            $hist = Join-Path $BlenderExe.DirectoryName "portable\config\fresing_pccheck"
            $block = Join-Path $hist "last_run.txt"
            if (Test-Path -LiteralPath $block) {
                Copy-Item -LiteralPath $block -Destination (Join-Path $OutDir "$pcTag`_last_run.txt")
            } else {
                Problem "the PC check left no numbers in $hist"
            }
            $Summary += "| PC check, $pcMode (Tools-folder shortcut) | finished, judged below | $secs s |"
        }
        }
        $env:FRESING_PCCHECK_HEAVY_SMALL = ""
        $env:FRESING_PCCHECK_ONLY = ""
    }
}

$table = @("### Windows install ($(if ($Uninstall) { 'uninstall' } elseif ($Part -ne 'all') { "install, part $($Part.ToUpper())" } else { 'install' })): $(if ($Problems) { 'FAILED' } else { 'passed' })", "",
           "| Step | Result | Time |", "| --- | --- | --- |") + $Summary
if ($Problems) { $table += @("", "**Problems:**", "") + ($Problems | ForEach-Object { "- $_" }) }
$text = ($table -join "`n") + "`n"
Write-Host $text
if ($env:GITHUB_STEP_SUMMARY) { Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Value $text -Encoding utf8 }
if ($Problems) { exit 1 }
