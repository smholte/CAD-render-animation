<#
.SYNOPSIS
  Installs Fresing Render: a pinned, portable Blender + the Fresing Render extension,
  the app layout, and shortcuts. No admin rights needed.

.DESCRIPTION
  Run "Install.bat" (double-click) next to this script. It:
    1. downloads Blender (pinned version) from download.blender.org, or uses a Blender zip
       placed next to this script, and checks its SHA-256 checksum
    2. unpacks it to %LOCALAPPDATA%\FresingRender in portable mode (separate from any
       other Blender on this PC); settings of an earlier version are carried over
    3. installs the Fresing Render extension from the zip next to this script
    4. installs the app layout (application template) and sets a few preferences, among them
       Blender's online access: the app looks for updates on GitHub at start-up and installs
       them with one click (Update now); see docs/UPDATES.md
    5. creates the "Fresing Render" shortcut on the Desktop and in the Start menu (the only ones, task 0212) and,
       in the Tools folder of the install folder, "Self test", "PC check (quick)" / "(full)" / "(heavy)" / "(stress)",
       "Safe start" and "User guide"; an older install's extra shortcuts are removed

  Running it again repairs or upgrades an installation; projects and renders are not touched.

.PARAMETER InstallDir
  Where to install. Default: %LOCALAPPDATA%\FresingRender

.PARAMETER UpdateUrl
  Optional: another update address for the app (an index.json made by tools/build_release.py),
  e.g. file://SERVER/share/fresing/index.json. Without it the app uses GitHub (the newest release
  of github.com/smholte/CAD-render-animation); an address set earlier is kept.
  "-UpdateUrl default" goes back to GitHub. A plain network path works too:
  \\SERVER\share\fresing\index.json

.PARAMETER AccessToken
  No longer used (updates come from the public GitHub releases); accepted so old command lines still run.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "FresingRender"),
    [string]$UpdateUrl = "",
    [string]$AccessToken = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is very slow with its progress bar
if ($AccessToken) { Write-Host "Note: -AccessToken is no longer used and is ignored." -ForegroundColor Yellow }
# Full path without a trailing slash, so folder comparisons below are reliable.
$InstallDir = [IO.Path]::GetFullPath($InstallDir.TrimEnd('\', '/'))

# ---- pinned Blender -----------------------------------------------------------
$BlenderVersion = "5.2.3"
$BlenderSeries  = "5.2"
$BlenderZipName = "blender-$BlenderVersion-windows-x64.zip"
$BlenderUrl     = "https://download.blender.org/release/Blender$BlenderSeries/$BlenderZipName"
# from https://download.blender.org/release/Blender5.2/blender-5.2.3.sha256
$BlenderSha256  = "723f08a4401502561eb763cdeacf8745b31e5f3f154d287d3830d97cf75dc2fb"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

# The licence in one line, first (task 0206). Fresing Render is free software under the GPL, which asks for no "I agree".
$LicenceFile = Join-Path $Here "LICENSE"
$ShownVersion = ""
$zipFirst = Get-ChildItem -LiteralPath $Here -Filter "fresing_render-*.zip" -ErrorAction SilentlyContinue | Select-Object -Last 1
if ($zipFirst -and $zipFirst.Name -match '^fresing_render-(\d+(\.\d+)*)') { $ShownVersion = $Matches[1] }
Write-Host "Fresing Render $ShownVersion - GPL-3.0-or-later, no warranty. Licence: $LicenceFile" -ForegroundColor Cyan

# Older Windows 10 PowerShell may default to TLS 1.0; download.blender.org needs TLS 1.2+.
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
# Company proxies: use the Windows login.
try { [Net.WebRequest]::DefaultWebProxy.Credentials = [Net.CredentialCache]::DefaultNetworkCredentials } catch { }

function Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }

# Virus scanners briefly lock freshly unpacked files: retry moves/deletes for a few seconds.
function Retry([scriptblock]$Action, [string]$What) {
    for ($i = 1; $i -le 15; $i++) {
        try { & $Action; return } catch {
            if ($i -eq 15) {
                throw "$What failed: $($_.Exception.Message) Close Explorer windows on the install folder and run the installer again."
            }
            Start-Sleep -Seconds 1
        }
    }
}

$BlenderDir = Join-Path $InstallDir "blender-$BlenderVersion-windows-x64"
$BlenderExe = Join-Path $BlenderDir "blender.exe"
$Portable   = Join-Path $BlenderDir "portable"

# Run Blender's command line. Blender writes warnings to stderr; in Windows PowerShell that
# counts as an error under "Stop", so success is judged by the exit code instead.
function Invoke-Blender([string[]]$BlenderArgs, [string]$What, [switch]$AllowFailure) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $BlenderExe @BlenderArgs 2>&1 | ForEach-Object { Write-Host "   $_" }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $old
    }
    if ($code -ne 0 -and -not $AllowFailure) { throw "$What failed (Blender exit code $code). See the messages above." }
    return ($code -eq 0)
}

# ---- 0. Fresing Render must not be running ------------------------------------------
$running = Get-Process -Name blender, blender-launcher, "Fresing Render" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path.StartsWith("$InstallDir\", [StringComparison]::OrdinalIgnoreCase) }
if ($running) {
    throw ("Fresing Render is still open, or a render queue is still running in the background. " +
           "Close Fresing Render (save your work first); a running render queue can be stopped in the app " +
           "(panel 7) or ended in Task Manager (Fresing Render or blender.exe). Then run the installer again.")
}

# ---- 1. Blender -----------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

if (Test-Path -LiteralPath $BlenderExe) {
    Step "Blender $BlenderVersion is already installed"
} else {
    $zip = Join-Path $Here $BlenderZipName
    $downloaded = $false
    if (-not (Test-Path -LiteralPath $zip)) {
        $zip = Join-Path $InstallDir $BlenderZipName
        if (-not (Test-Path -LiteralPath $zip)) {
            Step "Downloading Blender $BlenderVersion (about 400 MB, this can take a few minutes)"
            $part = "$zip.part"
            $ok = $false
            try {
                Import-Module BitsTransfer -ErrorAction Stop
                Start-BitsTransfer -Source $BlenderUrl -Destination $part -Description "Blender $BlenderVersion" -ErrorAction Stop
                $ok = $true
            } catch {
                Write-Host "   (BITS download not available, using a plain download)"
            }
            if (-not $ok) { Invoke-WebRequest -Uri $BlenderUrl -OutFile $part -UseBasicParsing }
            Move-Item -LiteralPath $part -Destination $zip -Force
            $downloaded = $true
        }
    }
    Step "Checking the download"
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLower()
    if ($hash -ne $BlenderSha256) {
        if ($downloaded -or $zip.StartsWith($InstallDir)) { Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue }
        if ($downloaded -or $zip.StartsWith($InstallDir)) {
            throw "The Blender download was damaged (checksum mismatch). Run the installer again."
        }
        throw "The Blender zip next to the installer ($zip) is damaged or the wrong version. Delete or replace it, then run the installer again."
    }
    Step "Unpacking Blender"
    # Unpack into a staging folder first: the Blender folder only appears once it is complete,
    # so an interrupted unpack is redone on the next run instead of looking "installed".
    $Staging = Join-Path $InstallDir "_unpack"
    if (Test-Path -LiteralPath $Staging) { Retry { Remove-Item -LiteralPath $Staging -Recurse -Force } "Removing an old unpack folder" }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $Staging)
    $unpacked = Join-Path $Staging "blender-$BlenderVersion-windows-x64"
    if (-not (Test-Path -LiteralPath (Join-Path $unpacked "blender.exe"))) { throw "The Blender zip did not contain blender.exe" }
    if (Test-Path -LiteralPath $BlenderDir) {
        # damaged earlier install (e.g. blender.exe quarantined): keep its settings
        $keep = Join-Path $BlenderDir "portable"
        if (Test-Path -LiteralPath $keep) {
            Retry { Move-Item -LiteralPath $keep -Destination (Join-Path $unpacked "portable") } "Keeping the old settings"
        }
        Retry { Remove-Item -LiteralPath $BlenderDir -Recurse -Force } "Removing the damaged Blender folder"
    }
    Retry { Move-Item -LiteralPath $unpacked -Destination $BlenderDir } "Moving Blender into place"
    Remove-Item -LiteralPath $Staging -Recurse -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path -LiteralPath $BlenderExe)) { throw "Blender was not unpacked to $BlenderDir" }
    if ($zip.StartsWith($InstallDir)) { Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue }
}

# Portable mode: settings live next to blender.exe, separate from any other Blender.
# When upgrading Blender, carry the settings (extension, preferences, library paths, cache) over
# from the previous Blender folder and remove that folder.
$older = Get-ChildItem -LiteralPath $InstallDir -Directory -Filter "blender-*-windows-x64" |
    Where-Object { $_.Name -ne (Split-Path -Leaf $BlenderDir) }
foreach ($old in $older) {
    $oldPortable = Join-Path $old.FullName "portable"
    if ((Test-Path -LiteralPath $oldPortable) -and -not (Test-Path -LiteralPath $Portable)) {
        Step "Moving settings from $($old.Name)"
        Move-Item -LiteralPath $oldPortable -Destination $Portable
    }
    Step "Removing the previous Blender ($($old.Name))"
    Remove-Item -LiteralPath $old.FullName -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $Portable | Out-Null

# ---- 2. Extension -----------------------------------------------------------------
$ExtRoot = Join-Path $Portable "extensions"
function Installed-Manifest([string]$repo) { Join-Path $ExtRoot "$repo\fresing_render\blender_manifest.toml" }

# The zip next to this script (newest version if there are several)
$zipExt = Get-ChildItem -LiteralPath $Here -Filter "fresing_render-*.zip" |
    Where-Object { $_.Name -match '^fresing_render-(\d+(\.\d+)*)' } |
    Sort-Object { [version]([regex]::Match($_.Name, '^fresing_render-(\d+(\.\d+)*)').Groups[1].Value) } |
    Select-Object -Last 1
if (-not $zipExt) { throw "fresing_render-<version>.zip not found next to the installer" }

# Before 0.2.16 an install with -UpdateUrl used a Blender extension repository called "fresing".
# The app now updates itself (Update now), always from the copy in "user_default": remove the old one.
$old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
$repoList = (& $BlenderExe --command extension repo-list 2>&1) -join "`n"
$ErrorActionPreference = $old
$OldRepoUrl = ""
if ($repoList -match "(?m)^fresing:") {
    # keep its address: the app asks there instead of GitHub (unless -UpdateUrl says otherwise)
    $inRepo = $false
    foreach ($line in ($repoList -split "`n")) {
        if ($line -match '^\S') { $inRepo = ($line -match '^fresing:') ; continue }
        if ($inRepo -and $line -match '^\s+url:\s*"([^"]+)"') { $OldRepoUrl = $Matches[1] }
    }
    Step "Removing the old update repository (the app now updates itself)"
    if (Test-Path -LiteralPath (Installed-Manifest "fresing")) {
        Invoke-Blender @("--command", "extension", "remove", "fresing.fresing_render") "Removing the old copy" -AllowFailure | Out-Null
    }
    Invoke-Blender @("--command", "extension", "repo-remove", "fresing") "Removing the old update repository" -AllowFailure | Out-Null
}

Step "Installing $($zipExt.Name)"
Invoke-Blender @("--command", "extension", "install-file", "--repo", "user_default", "--enable", $zipExt.FullName) "Installing the extension" | Out-Null
$Manifest = Installed-Manifest "user_default"
$Expected = [regex]::Match($zipExt.Name, '^fresing_render-(\d+(\.\d+)*)').Groups[1].Value

# Blender can report success even when the install failed: check the files.
if (-not (Test-Path -LiteralPath $Manifest)) { throw "The extension was not installed (missing $Manifest)." }
$m = Select-String -LiteralPath $Manifest -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
if (-not $m) { throw "The installed extension looks damaged (no version in $Manifest)." }
$ver = $m.Matches[0].Groups[1].Value
if ($Expected -and $ver -ne $Expected) { throw "Installed version is $ver, expected $Expected." }
Write-Host "   Fresing Render $ver installed"

# ---- 3. App template + preferences -----------------------------------------------------
Step "Installing the Fresing Render app layout"
$TemplateSrc = Join-Path $Here "app_template\fresing_render"     # the same files ship inside the extension
$TemplateDst = Join-Path $Portable "scripts\startup\bl_app_templates_user\fresing_render"
if (-not (Test-Path -LiteralPath (Join-Path $TemplateSrc "__init__.py"))) {
    throw "The app_template folder is missing next to the installer: unzip the whole folder and run Install.bat again."
}
if (Test-Path -LiteralPath $TemplateDst) { Retry { Remove-Item -LiteralPath $TemplateDst -Recurse -Force } "Replacing the app layout" }
New-Item -ItemType Directory -Force -Path $TemplateDst | Out-Null
Get-ChildItem -LiteralPath $TemplateSrc | Copy-Item -Destination $TemplateDst -Recurse -Force

# Licence files next to the app (task 0206): Fresing Render's own licence, the notices and the licence texts of the
# libraries. They also ship inside the extension (the app's About window opens those); this copy is for whoever looks
# in the install folder. Blender's own "license" folder comes with the Blender zip as it is: check it is there.
$LicenceDst = Join-Path $InstallDir "licenses"
if (Test-Path -LiteralPath (Join-Path $Here "LICENSE")) {
    if (Test-Path -LiteralPath $LicenceDst) { Retry { Remove-Item -LiteralPath $LicenceDst -Recurse -Force } "Replacing the licence files" }
    New-Item -ItemType Directory -Force -Path $LicenceDst | Out-Null
    foreach ($f in "LICENSE", "THIRD-PARTY-NOTICES.md", "COMPANY-USE.md") {
        if (Test-Path -LiteralPath (Join-Path $Here $f)) { Copy-Item -LiteralPath (Join-Path $Here $f) -Destination $LicenceDst -Force }
    }
    if (Test-Path -LiteralPath (Join-Path $Here "licenses\third-party")) {
        Copy-Item -LiteralPath (Join-Path $Here "licenses\third-party") -Destination $LicenceDst -Recurse -Force
    }
    Write-Host "   Licence files: $LicenceDst"
} else {
    Write-Host "   (no licence files next to the installer - the extension carries its own copy)" -ForegroundColor Yellow
}
if (-not (Test-Path -LiteralPath (Join-Path $BlenderDir "license"))) {
    Write-Host "   (Blender's own license folder is missing from $BlenderDir - Blender's licence texts are on https://www.blender.org/about/license/)" -ForegroundColor Yellow
}

# Update address for the app (core/updates.py reads <portable>\config\fresing_update.json).
$ConfigDir = Join-Path $Portable "config"
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
$UrlFile = Join-Path $ConfigDir "fresing_update.json"
if (-not $UpdateUrl -and $OldRepoUrl -and -not (Test-Path -LiteralPath $UrlFile)) {
    $UpdateUrl = $OldRepoUrl                    # the address of the old update repository
}
if ($UpdateUrl -eq "default") {
    Remove-Item -LiteralPath $UrlFile -Force -ErrorAction SilentlyContinue
} elseif ($UpdateUrl) {
    Step "Update address: $UpdateUrl"
    @{ url = $UpdateUrl } | ConvertTo-Json | Set-Content -LiteralPath $UrlFile -Encoding UTF8
}
$UpdateFrom = "GitHub (newest release)"
if (Test-Path -LiteralPath $UrlFile) {
    try { $UpdateFrom = (Get-Content -LiteralPath $UrlFile -Raw | ConvertFrom-Json).url } catch { $UpdateFrom = "?" }
}

$PrefsScript = Join-Path $InstallDir "set_prefs.py"
@"
import bpy
p = bpy.context.preferences
p.filepaths.use_relative_paths = True
p.view.show_tooltips_python = False
p.system.use_online_access = True          # the app looks for updates at start-up (Update now)
for repo in p.extensions.repos:            # Blender's own extension repositories do not sync at start (task 0206)
    if repo.use_remote_url:
        repo.use_sync_on_startup = False
import addon_utils
names = [m.__name__ for m in addon_utils.modules() if m.__name__.endswith(".fresing_render")]
for name in names:
    addon_utils.enable(name, default_set=True)   # repairs a disabled extension
bpy.ops.wm.save_userpref()
"@ | Set-Content -LiteralPath $PrefsScript -Encoding ASCII
Invoke-Blender @("--background", "--python-exit-code", "1", "--python", $PrefsScript) "Setting preferences" | Out-Null

# ---- 4. Self-test launcher + shortcuts ------------------------------------------------
$Desktop = [Environment]::GetFolderPath("Desktop")
$Launcher = Join-Path $InstallDir "selftest_launcher.py"
@"
import importlib, addon_utils
for mod in addon_utils.modules():
    if mod.__name__.endswith("fresing_render"):
        addon_utils.enable(mod.__name__, default_set=True)
        importlib.import_module(mod.__name__ + ".selftest").main()
        break
else:
    print("Fresing Render is not installed in this Blender")
"@ | Set-Content -LiteralPath $Launcher -Encoding ASCII

# The Fresing icon (task 0169): it ships inside the extension; a copy in the install folder does not move when an
# update replaces the extension, so every shortcut points there (the app copies it again at start when it changed).
$IconFile = Join-Path $InstallDir "fresing-render.ico"
$ShippedIcon = Join-Path (Split-Path -Parent $Manifest) "brand\fresing-render.ico"
if (Test-Path -LiteralPath $ShippedIcon) { Copy-Item -LiteralPath $ShippedIcon -Destination $IconFile -Force }
$IconLoc = if (Test-Path -LiteralPath $IconFile) { "$IconFile,0" } else { "$BlenderExe,0" }

$Shell = New-Object -ComObject WScript.Shell
function MakeShortcut($path, $target, $arguments, $description) {
    $lnk = $Shell.CreateShortcut($path)
    $lnk.TargetPath = $target
    $lnk.Arguments = $arguments
    $lnk.WorkingDirectory = $BlenderDir
    $lnk.IconLocation = $IconLoc
    $lnk.Description = $description
    $lnk.Save()
}
# blender-launcher.exe starts Blender without a console window
$GuiExe = Join-Path $BlenderDir "blender-launcher.exe"
if (-not (Test-Path -LiteralPath $GuiExe)) { $GuiExe = $BlenderExe }
# Task 0212: only "Fresing Render" on the Desktop and in the Start menu (directly in Programs, one entry); the extras
# (self-test, PC checks, safe start, user guide) in the Tools folder of the install folder and in the app's Fresing menu.
$Programs = [Environment]::GetFolderPath("Programs")
$OldMenu = Join-Path $Programs "Fresing Render"
$Tools = Join-Path $InstallDir "Tools"
New-Item -ItemType Directory -Force -Path $Tools | Out-Null

Step "Creating shortcuts"
# An install before 0212 had the extras on the Desktop and in a Start-menu folder "Fresing Render": remove them by
# name, and only when their target lies inside the install folder (never someone else's shortcut).
function Remove-OldLink([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    try { $t = $Shell.CreateShortcut($path).TargetPath } catch { $t = "" }
    if ($t -and $t.StartsWith("$InstallDir\", [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        Write-Host "   removed the old shortcut '$(Split-Path -Leaf $path)' (now in the Tools folder)"
    }
}
foreach ($n in @("Fresing Render - PC check.lnk", "Fresing Render - PC check (heavy).lnk")) { Remove-OldLink (Join-Path $Desktop $n) }
# the app's own old Start-menu shortcut is moved, not made again: a "Pin to Start" made from it stays (as the app does)
$OldApp = Join-Path $OldMenu "Fresing Render.lnk"
$NewApp = Join-Path $Programs "Fresing Render.lnk"
if ((Test-Path -LiteralPath $OldApp) -and -not (Test-Path -LiteralPath $NewApp)) {
    try { $t = $Shell.CreateShortcut($OldApp).TargetPath } catch { $t = "" }
    if ($t -and $t.StartsWith("$InstallDir\", [StringComparison]::OrdinalIgnoreCase)) {
        Move-Item -LiteralPath $OldApp -Destination $NewApp -Force -ErrorAction SilentlyContinue
    }
}
foreach ($n in @("Fresing Render.lnk", "Fresing Render - safe start.lnk", "Fresing Render - Self test.lnk",
                 "Fresing Render - PC check (quick).lnk", "Fresing Render - PC check (full).lnk",
                 "Fresing Render - PC check (heavy).lnk", "Fresing Render - User guide.lnk")) { Remove-OldLink (Join-Path $OldMenu $n) }
# empty apart from Explorer's own desktop.ini: the folder goes
if ((Test-Path -LiteralPath $OldMenu) -and -not (Get-ChildItem -LiteralPath $OldMenu -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne "desktop.ini" })) {
    Remove-Item -LiteralPath $OldMenu -Recurse -Force -ErrorAction SilentlyContinue
}

MakeShortcut (Join-Path $Desktop "Fresing Render.lnk") $GuiExe "--app-template fresing_render" "Render STEP models"
MakeShortcut (Join-Path $Programs "Fresing Render.lnk") $GuiExe "--app-template fresing_render" "Render STEP models"
# task 0177: the app's shortcuts are pointed at "Fresing Render.exe" below; this one always starts Blender's own launcher
MakeShortcut (Join-Path $Tools "Safe start.lnk") $GuiExe "--app-template fresing_render" "Starts Fresing Render with Blender's own program. Use it only if Fresing Render does not start from its usual shortcut"
MakeShortcut (Join-Path $Tools "Self test.lnk") $BlenderExe "--background --python `"$Launcher`" -- `"$Desktop`"" "Check this PC and write a report on the Desktop"

# PC check (task 0032): every main function with the test models; the launcher lives inside the installed
# extension, so an update brings the new check along. A STEP file dropped on a shortcut is tested too.
# (An app updated with Update now makes the Tools folder's shortcuts itself when they are missing: appicon.py.)
$PcCheck = Join-Path (Split-Path -Parent $Manifest) "pccheck\launcher.py"
if (Test-Path -LiteralPath $PcCheck) {
    MakeShortcut (Join-Path $Tools "PC check (quick).lnk") $BlenderExe "--background --python `"$PcCheck`" -- `"$Desktop`" quick" "Check every main function quickly (about 3 minutes). Drop a STEP file on it to test your own model too"
    MakeShortcut (Join-Path $Tools "PC check (full).lnk") $BlenderExe "--background --python `"$PcCheck`" -- `"$Desktop`" full" "Check every function of the app on this PC (about 15 minutes). Drop a STEP file on it to test your own model too"
    # Heavy (task 0033): a big generated machine, 4K pictures and a 10 s video; 10-20 minutes. Started on purpose.
    MakeShortcut (Join-Path $Tools "PC check (heavy).lnk") $BlenderExe "--background --python `"$PcCheck`" -- `"$Desktop`" heavy" "Load this PC like real work: a big machine, 4K pictures and a 10 second video (about 10 to 20 minutes). Cancel it in the app: Help > Cancel Fresing Render PC check"
    # Stress (task 0315): a made-up 10,000-part model, every heavy action timed; 10-20 minutes. Started on purpose.
    MakeShortcut (Join-Path $Tools "PC check (stress).lnk") $BlenderExe "--background --python `"$PcCheck`" -- `"$Desktop`" stress" "Stress test with a made-up 10,000-part model: every heavy action timed and compared with the last Stress run (takes long: about 10 to 20 minutes). Cancel it in the app: Help > Cancel Fresing Render PC check"
}

# The user guide lives inside the installed extension (Help > Fresing Render user guide opens the same
# file), so it always matches the installed version. The shortcut opens it in the web browser.
$Guide = Join-Path (Split-Path -Parent $Manifest) "guide\user_guide.html"
$GuideLnk = Join-Path $Tools "User guide.lnk"
if (Test-Path -LiteralPath $Guide) {
    $lnk = $Shell.CreateShortcut($GuideLnk)
    $lnk.TargetPath = $Guide
    $lnk.IconLocation = $IconLoc
    $lnk.Description = "How to use Fresing Render, step by step"
    $lnk.Save()
} else {
    Write-Host "   (no user guide in this version)"
    Remove-Item -LiteralPath $GuideLnk -Force -ErrorAction SilentlyContinue
}

# The app's ID on the shortcuts that start the app (task 0169): the running app sets the same ID, so the taskbar
# groups its window under the Fresing icon and a pinned Fresing Render stays Fresing. WScript.Shell cannot set it:
# the extension's own code does (fresing_render/appicon.py), the same that refreshes older installs at start.
# Task 0177: the same step makes "Fresing Render.exe" (blender.exe under the app's name and icon, winexe.py; checked
# by starting it once) and points the app's shortcuts at it, so Task Manager says "Fresing Render". When the copy
# cannot be used (Smart App Control on, or it did not start) they stay on blender-launcher.exe.
$ShortcutScript = Join-Path $InstallDir "set_shortcuts.py"
@"
import importlib, sys, addon_utils
folder, desktop, programs, appdata = (sys.argv[sys.argv.index("--") + 1:] + ["", "", "", ""])[:4]
for mod in addon_utils.modules():
    if mod.__name__.endswith("fresing_render"):
        icon = importlib.import_module(mod.__name__ + ".appicon")
        ico = icon.ensure_icon(folder)
        import bpy
        target = icon.app_target_for(bpy.app.binary_path, ico)
        print("The app starts: " + (target or "(Blender's own programs)"))
        paths = icon.shortcut_paths(desktop, programs, appdata, icon.tools_dir(folder))
        done = icon.refresh_shortcuts(folder, ico, paths, target)
        print("Shortcuts: " + ("; ".join(done) if done else "already right"))
        # task 0217: the Toolbox folder and the app's manifest (start = what the shortcuts start); the app writes it
        # again at every start, so an update keeps it right
        try:
            tb = importlib.import_module(mod.__name__ + ".core.toolbox")
            ver = importlib.import_module(mod.__name__).__version__
            exe = importlib.import_module(mod.__name__ + ".winexe").app_exe(bpy.app.binary_path)
            path = tb.install(tb.home(), str(ver), exe or target, ["--app-template", "fresing_render"])
            print("Toolbox folder: " + str(path))
        except Exception as exc:
            print("Toolbox folder: not made (" + str(exc) + "); the app tries again at its start")
        break
else:
    sys.exit("Fresing Render is not installed in this Blender")
"@ | Set-Content -LiteralPath $ShortcutScript -Encoding ASCII
$ok = Invoke-Blender @("--background", "--python-exit-code", "1", "--python", $ShortcutScript, "--",
                       $InstallDir, $Desktop, $Programs, $env:APPDATA) "Setting the app's name, ID and program on the shortcuts" -AllowFailure
if (-not $ok) { Write-Host "   (the shortcuts keep their icon; the app sets their ID at its next start)" -ForegroundColor Yellow }

# ---- 4b. The graphics card (task 0296) ------------------------------------------------------------
# Windows' per-user graphics preference "High performance" for the app's programs - what Settings > System > Display >
# Graphics writes (HKCU\Software\Microsoft\DirectX\UserGpuPreferences, value name = the program's full path). Only
# where the user has not chosen (no value, or "Let Windows decide"); other settings in the value are kept. The app does
# the same at its start (wingpu.py), Update now too, and the uninstaller removes the values of this install folder.
Step "Asking Windows to run Fresing Render on the graphics card"
try {
    $GpuKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey("Software\Microsoft\DirectX\UserGpuPreferences")
    try {
        foreach ($exe in @($BlenderExe, (Join-Path $BlenderDir "Fresing Render.exe"))) {
            if (-not (Test-Path -LiteralPath $exe)) { continue }
            $old = [string]$GpuKey.GetValue($exe, "")
            $parts = @($old -split ";" | Where-Object { $_.Trim() })
            $pref = @($parts | Where-Object { $_ -match "^\s*GpuPreference\s*=" })
            $chosen = if ($pref) { ($pref[0] -split "=", 2)[1].Trim() } else { "" }
            if ($chosen -and $chosen -ne "0") {
                Write-Host "   $([IO.Path]::GetFileName($exe)): kept the choice made in Windows' Graphics settings ($old)"
                continue
            }
            $keep = @($parts | Where-Object { $_ -notmatch "^\s*GpuPreference\s*=" } | ForEach-Object { $_.Trim() + ";" })
            $new = ($keep -join "") + "GpuPreference=2;"
            $GpuKey.SetValue($exe, $new, [Microsoft.Win32.RegistryValueKind]::String)
            Write-Host "   $([IO.Path]::GetFileName($exe)): High performance"
        }
    } finally { $GpuKey.Close() }
} catch {
    Write-Host "   (could not set Windows' graphics preference: $($_.Exception.Message); the app tries again at its start)" -ForegroundColor Yellow
}

# ---- 5. Settings > Apps > Installed apps (task 0265) ---------------------------------------------
# One per-user key (no admin rights). Its Uninstall runs the uninstaller kept in the Tools folder; a copy of that file
# ships inside the extension too, so Update now and the app's start keep it and the entry right (core/installed_apps.py).
Step "Adding Fresing Render to Windows' Installed apps"
try {
    $UninstallDst = Join-Path $Tools "Uninstall-FresingRender.ps1"
    $UninstallSrc = Join-Path $Here "Uninstall-FresingRender.ps1"
    if (Test-Path -LiteralPath $UninstallSrc) { Copy-Item -LiteralPath $UninstallSrc -Destination $UninstallDst -Force }
    if (Test-Path -LiteralPath $UninstallDst) {
        $sizeKb = [int][math]::Max(1, [math]::Round(((Get-ChildItem -LiteralPath $InstallDir -Recurse -File -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum) / 1KB))
        $uninstallCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$UninstallDst`" -InstallDir `"$InstallDir`""
        $AppsKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\FresingRender"
        $oldDate = ""
        if (Test-Path -LiteralPath $AppsKey) { $oldDate = [string](Get-ItemProperty -LiteralPath $AppsKey).InstallDate }
        New-Item -Path $AppsKey -Force | Out-Null
        $values = [ordered]@{
            DisplayName = "Fresing Render"; DisplayVersion = "$ver"; Publisher = "Fresing"
            DisplayIcon = $(if (Test-Path -LiteralPath $IconFile) { $IconFile } else { $BlenderExe })
            InstallLocation = $InstallDir
            InstallDate = $(if ($oldDate) { $oldDate } else { (Get-Date).ToString("yyyyMMdd") })
            URLInfoAbout = "https://github.com/smholte/CAD-render-animation"
            HelpLink = "https://smholte.github.io/CAD-render-animation/"
            UninstallString = "$uninstallCmd -Pause"
            QuietUninstallString = $uninstallCmd
        }
        foreach ($k in $values.Keys) { New-ItemProperty -LiteralPath $AppsKey -Name $k -Value $values[$k] -PropertyType String -Force | Out-Null }
        foreach ($k in "NoModify", "NoRepair") { New-ItemProperty -LiteralPath $AppsKey -Name $k -Value 1 -PropertyType DWord -Force | Out-Null }
        New-ItemProperty -LiteralPath $AppsKey -Name "EstimatedSize" -Value $sizeKb -PropertyType DWord -Force | Out-Null
        Write-Host "   Installed apps: Fresing Render $ver ($sizeKb KB)"
    } else {
        Write-Host "   (Uninstall-FresingRender.ps1 is not next to the installer - no entry in Installed apps)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   (could not add the entry to Installed apps: $($_.Exception.Message); the app tries again at its start)" -ForegroundColor Yellow
}

Set-Content -LiteralPath (Join-Path $InstallDir "installed.txt") -Value "Fresing Render $ver installed $(Get-Date -Format s)`r`nBlender $BlenderVersion`r`nUpdates from: $UpdateFrom"

Write-Host ""
Write-Host "Done. Start 'Fresing Render' from the Desktop." -ForegroundColor Green
Write-Host "New versions: the app shows 'Update available' at start-up; one click on Update now installs them."
Write-Host "Tip: run the self-test once (in the app: Fresing > Tools and checks > Run the self-test); it writes a report on the Desktop."
Write-Host "After an update: Fresing > Tools and checks > PC check tests every main function on this PC."
Write-Host "Self-test, PC checks, safe start and user guide are also shortcuts in $Tools"
