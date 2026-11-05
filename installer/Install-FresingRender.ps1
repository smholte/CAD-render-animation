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
    5. creates "Fresing Render" and "Fresing Render - Self test" shortcuts, and a Start-menu
       shortcut "Fresing Render - User guide" (the guide inside the installed extension)

  Running it again repairs or upgrades an installation; projects and renders are not touched.

.PARAMETER InstallDir
  Where to install. Default: %LOCALAPPDATA%\FresingRender

.PARAMETER UpdateUrl
  Optional: another update address for the app (an index.json made by tools/build_release.py),
  e.g. file://SERVER/share/fresing/index.json. Without it the app uses GitHub (the newest release
  of github.com/smholte/CAD-render-animation); an address set earlier is kept.
  "-UpdateUrl default" goes back to GitHub.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "FresingRender"),
    [string]$UpdateUrl = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is very slow with its progress bar
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
$running = Get-Process -Name blender, blender-launcher -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path.StartsWith("$InstallDir\", [StringComparison]::OrdinalIgnoreCase) }
if ($running) {
    throw ("Fresing Render is still open, or a render queue is still running in the background. " +
           "Close Fresing Render (save your work first); a running render queue can be stopped in the app " +
           "(panel 7) or ended in Task Manager (blender.exe). Then run the installer again.")
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

# Before 0.2.14 an install with -UpdateUrl used a Blender extension repository called "fresing".
# The app now updates itself (Update now), always from the copy in "user_default": remove the old one.
$old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
$repoList = (& $BlenderExe --command extension repo-list 2>&1) -join "`n"
$ErrorActionPreference = $old
if ($repoList -match "(?m)^fresing:") {
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

# Update address for the app (core/updates.py reads <portable>\config\fresing_update.json).
$ConfigDir = Join-Path $Portable "config"
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
$UrlFile = Join-Path $ConfigDir "fresing_update.json"
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

$Shell = New-Object -ComObject WScript.Shell
function MakeShortcut($path, $target, $arguments, $description) {
    $lnk = $Shell.CreateShortcut($path)
    $lnk.TargetPath = $target
    $lnk.Arguments = $arguments
    $lnk.WorkingDirectory = $BlenderDir
    $lnk.IconLocation = "$BlenderExe,0"
    $lnk.Description = $description
    $lnk.Save()
}
# blender-launcher.exe starts Blender without a console window
$GuiExe = Join-Path $BlenderDir "blender-launcher.exe"
if (-not (Test-Path -LiteralPath $GuiExe)) { $GuiExe = $BlenderExe }
$StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Fresing Render"
New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null

Step "Creating shortcuts"
MakeShortcut (Join-Path $Desktop "Fresing Render.lnk") $GuiExe "--app-template fresing_render" "Render STEP models"
MakeShortcut (Join-Path $StartMenu "Fresing Render.lnk") $GuiExe "--app-template fresing_render" "Render STEP models"
MakeShortcut (Join-Path $StartMenu "Fresing Render - Self test.lnk") $BlenderExe "--background --python `"$Launcher`" -- `"$Desktop`"" "Check this PC and write a report on the Desktop"

# The user guide lives inside the installed extension (Help > Fresing Render user guide opens the same
# file), so it always matches the installed version. The shortcut opens it in the web browser.
$Guide = Join-Path (Split-Path -Parent $Manifest) "guide\user_guide.html"
$GuideLnk = Join-Path $StartMenu "Fresing Render - User guide.lnk"
if (Test-Path -LiteralPath $Guide) {
    $lnk = $Shell.CreateShortcut($GuideLnk)
    $lnk.TargetPath = $Guide
    $lnk.Description = "How to use Fresing Render, step by step"
    $lnk.Save()
} else {
    Write-Host "   (no user guide in this version)"
    Remove-Item -LiteralPath $GuideLnk -Force -ErrorAction SilentlyContinue
}

Set-Content -LiteralPath (Join-Path $InstallDir "installed.txt") -Value "Fresing Render $ver installed $(Get-Date -Format s)`r`nBlender $BlenderVersion`r`nUpdates from: $UpdateFrom"

Write-Host ""
Write-Host "Done. Start 'Fresing Render' from the Desktop." -ForegroundColor Green
Write-Host "New versions: the app shows 'Update available' at start-up; one click on Update now installs them."
Write-Host "Tip: run 'Fresing Render - Self test' from the Start menu once; it writes a report on the Desktop."
