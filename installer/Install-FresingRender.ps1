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
    3. installs the Fresing Render extension: from the update repository when -UpdateUrl
       is given (later updates are then one click), otherwise from the zip next to this script
    4. installs the app layout (application template) and sets a few preferences
    5. creates "Fresing Render" and "Fresing Render - Self test" shortcuts

  Running it again repairs or upgrades an installation; projects and renders are not touched.

.PARAMETER InstallDir
  Where to install. Default: %LOCALAPPDATA%\FresingRender

.PARAMETER UpdateUrl
  Optional URL of the private update repository (index.json), e.g.
  https://updates.example.com/fresing-render/index.json  or  file://SERVER/share/fresing/index.json

.PARAMETER AccessToken
  Optional access token for the update repository.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "FresingRender"),
    [string]$UpdateUrl = "",
    [string]$AccessToken = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is very slow with its progress bar

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
    Where-Object { $_.Path -and $_.Path.StartsWith($InstallDir, [StringComparison]::OrdinalIgnoreCase) }
if ($running) {
    throw "Fresing Render is still open. Close it (save your work first) and run the installer again."
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
        throw "The Blender zip ($zip) is damaged or not the expected version (checksum mismatch). Run the installer again."
    }
    Step "Unpacking Blender"
    if (Test-Path -LiteralPath $BlenderDir) { Remove-Item -LiteralPath $BlenderDir -Recurse -Force }   # half-finished earlier attempt
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $InstallDir)
    if (-not (Test-Path -LiteralPath $BlenderExe)) { throw "Blender was not unpacked to $BlenderDir" }
    if ($zip.StartsWith($InstallDir)) { Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue }
}

# Portable mode: settings live next to blender.exe, separate from any other Blender.
# When upgrading Blender, carry the settings (extension, preferences, library paths, cache) over
# from the previous Blender folder and remove that folder.
$older = Get-ChildItem -LiteralPath $InstallDir -Directory -Filter "blender-*-windows-x64" |
    Where-Object { $_.FullName -ne $BlenderDir }
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

if ($UpdateUrl) {
    Step "Connecting to the update repository"
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $repoList = (& $BlenderExe --command extension repo-list 2>&1) -join "`n"
    $ErrorActionPreference = $old
    if ($repoList -notmatch "(?m)^fresing:") {
        $repoArgs = @("--command", "extension", "repo-add", "--name", "Fresing", "--url", $UpdateUrl)
        if ($AccessToken) { $repoArgs += @("--access-token", $AccessToken) }
        $repoArgs += @("fresing")
        Invoke-Blender $repoArgs "Adding the update repository" | Out-Null
    } else {
        Write-Host "   Update repository already set up"
    }
    if (Test-Path -LiteralPath (Installed-Manifest "user_default")) {
        Invoke-Blender @("--command", "extension", "remove", "user_default.fresing_render") "Removing the zip-installed copy" -AllowFailure | Out-Null
    }
    if (Test-Path -LiteralPath (Installed-Manifest "fresing")) {
        Step "Updating Fresing Render"
        Invoke-Blender @("--online-mode", "--command", "extension", "update", "--sync") "Updating the extension" | Out-Null
    } else {
        Step "Installing Fresing Render from the update repository"
        Invoke-Blender @("--online-mode", "--command", "extension", "install", "--sync", "--enable", "fresing_render") "Installing the extension" | Out-Null
    }
    $Manifest = Installed-Manifest "fresing"
    $Expected = ""
} else {
    $ext = Get-ChildItem -LiteralPath $Here -Filter "fresing_render-*.zip" | Sort-Object Name | Select-Object -Last 1
    if (-not $ext) { throw "fresing_render-<version>.zip not found next to the installer" }
    if (Test-Path -LiteralPath (Installed-Manifest "fresing")) {
        Invoke-Blender @("--command", "extension", "remove", "fresing.fresing_render") "Removing the repository copy" -AllowFailure | Out-Null
    }
    Step "Installing $($ext.Name)"
    Invoke-Blender @("--command", "extension", "install-file", "--repo", "user_default", "--enable", $ext.FullName) "Installing the extension" | Out-Null
    $Manifest = Installed-Manifest "user_default"
    $Expected = ($ext.BaseName -replace "^fresing_render-", "")
}

# Blender can report success even when the install failed: check the files.
if (-not (Test-Path -LiteralPath $Manifest)) { throw "The extension was not installed (missing $Manifest)." }
if ($Expected) {
    $ver = (Select-String -LiteralPath $Manifest -Pattern '^version\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
    if ($ver -ne $Expected) { throw "Installed version is $ver, expected $Expected." }
    Write-Host "   Fresing Render $ver installed"
}

# ---- 3. App template + preferences -----------------------------------------------------
Step "Installing the Fresing Render app layout"
$TemplateSrc = Join-Path $Here "app_template\fresing_render"
$TemplateDst = Join-Path $Portable "scripts\startup\bl_app_templates_user\fresing_render"
if (Test-Path -LiteralPath $TemplateDst) { Remove-Item -LiteralPath $TemplateDst -Recurse -Force }
New-Item -ItemType Directory -Force -Path $TemplateDst | Out-Null
Get-ChildItem -LiteralPath $TemplateSrc | Copy-Item -Destination $TemplateDst -Recurse -Force

$Online = if ($UpdateUrl) { "True" } else { "False" }
$PrefsScript = Join-Path $InstallDir "set_prefs.py"
@"
import bpy
p = bpy.context.preferences
p.filepaths.use_relative_paths = True
p.view.show_tooltips_python = False
if $Online:
    p.system.use_online_access = True          # needed for the update check
    for repo in p.extensions.repos:
        if repo.module == "fresing":
            repo.use_sync_on_startup = True    # show "update available" at start-up
bpy.ops.wm.save_userpref()
"@ | Set-Content -LiteralPath $PrefsScript -Encoding ASCII
Invoke-Blender @("--background", "--python", $PrefsScript) "Setting preferences" -AllowFailure | Out-Null

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

Set-Content -LiteralPath (Join-Path $InstallDir "installed.txt") -Value "Fresing Render installed $(Get-Date -Format s)`r`nBlender $BlenderVersion`r`nUpdate URL: $UpdateUrl"

Write-Host ""
Write-Host "Done. Start 'Fresing Render' from the Desktop." -ForegroundColor Green
Write-Host "Tip: run 'Fresing Render - Self test' from the Start menu once; it writes a report on the Desktop."
