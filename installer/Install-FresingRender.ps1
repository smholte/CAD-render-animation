<#
.SYNOPSIS
  Installs Fresing Render: a pinned, portable Blender + the Fresing Render extension,
  the app layout, and desktop shortcuts. No admin rights needed.

.DESCRIPTION
  Run "Install.bat" (double-click) next to this script. It:
    1. downloads Blender (pinned version) from download.blender.org, or uses a Blender zip
       placed next to this script, and checks its SHA-256 checksum
    2. unpacks it to %LOCALAPPDATA%\FresingRender in portable mode (separate from any
       other Blender on this PC)
    3. installs the Fresing Render extension (from the update repository when -UpdateUrl
       is given, so later updates are one click; otherwise from the zip next to this script)
    4. installs the app layout (application template)
    5. creates "Fresing Render" and "Fresing Render - Self test" shortcuts

  Running it again repairs or upgrades an installation; your projects are not touched.

.PARAMETER InstallDir
  Where to install. Default: %LOCALAPPDATA%\FresingRender

.PARAMETER UpdateUrl
  Optional URL of the private update repository (index.json). Example:
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
$ProgressPreference = "SilentlyContinue"   # makes downloads much faster in Windows PowerShell

# ---- pinned Blender -----------------------------------------------------------
$BlenderVersion = "5.2.3"
$BlenderSeries  = "5.2"
$BlenderZipName = "blender-$BlenderVersion-windows-x64.zip"
$BlenderUrl     = "https://download.blender.org/release/Blender$BlenderSeries/$BlenderZipName"
$BlenderSha256  = "723f08a4401502561eb763cdeacf8745b31e5f3f154d287d3830d97cf75dc2fb"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }

# ---- 1. Blender -----------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$BlenderDir = Join-Path $InstallDir "blender-$BlenderVersion-windows-x64"
$BlenderExe = Join-Path $BlenderDir "blender.exe"

if (Test-Path $BlenderExe) {
    Step "Blender $BlenderVersion is already installed"
} else {
    $zip = Join-Path $Here $BlenderZipName
    if (-not (Test-Path $zip)) {
        $zip = Join-Path $InstallDir $BlenderZipName
        if (-not (Test-Path $zip)) {
            Step "Downloading Blender $BlenderVersion (about 400 MB)"
            Invoke-WebRequest -Uri $BlenderUrl -OutFile $zip -UseBasicParsing
        }
    }
    Step "Checking the download"
    $hash = (Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLower()
    if ($hash -ne $BlenderSha256) {
        Remove-Item $zip -Force -ErrorAction SilentlyContinue
        throw "Checksum of $BlenderZipName does not match. The download was damaged; run the installer again."
    }
    Step "Unpacking Blender"
    if (Test-Path $BlenderDir) { Remove-Item $BlenderDir -Recurse -Force }   # half-finished earlier attempt
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $InstallDir)
    if (-not (Test-Path $BlenderExe)) { throw "Blender was not unpacked to $BlenderDir" }
    Remove-Item (Join-Path $InstallDir $BlenderZipName) -Force -ErrorAction SilentlyContinue
}

# Portable mode: settings live next to blender.exe, separate from any other Blender.
$Portable = Join-Path $BlenderDir "portable"
New-Item -ItemType Directory -Force -Path $Portable | Out-Null

# ---- 2. Extension -----------------------------------------------------------------
if ($UpdateUrl) {
    Step "Connecting to the update repository"
    $repoArgs = @("--command", "extension", "repo-add", "--name", "Fresing", "--url", $UpdateUrl)
    if ($AccessToken) { $repoArgs += @("--access-token", $AccessToken) }
    $repoArgs += @("fresing")
    & $BlenderExe @repoArgs 2>&1 | ForEach-Object { Write-Host "   $_" }
    Step "Installing Fresing Render from the update repository"
    & $BlenderExe --command extension install --sync --enable fresing_render 2>&1 | ForEach-Object { Write-Host "   $_" }
} else {
    $ext = Get-ChildItem -Path $Here -Filter "fresing_render-*.zip" | Sort-Object Name | Select-Object -Last 1
    if (-not $ext) { throw "fresing_render-<version>.zip not found next to the installer" }
    Step "Installing $($ext.Name)"
    & $BlenderExe --command extension install-file --repo user_default --enable $ext.FullName 2>&1 | ForEach-Object { Write-Host "   $_" }
}

# ---- 3. App template ------------------------------------------------------------------
Step "Installing the Fresing Render app layout"
$TemplateSrc = Join-Path $Here "app_template\fresing_render"
$TemplateDst = Join-Path $Portable "scripts\startup\bl_app_templates_user\fresing_render"
New-Item -ItemType Directory -Force -Path $TemplateDst | Out-Null
Copy-Item -Path (Join-Path $TemplateSrc "*") -Destination $TemplateDst -Recurse -Force

# ---- 4. Self-test launcher + shortcuts ------------------------------------------------
$Launcher = Join-Path $InstallDir "selftest_launcher.py"
@"
import sys, importlib, addon_utils
for mod in addon_utils.modules():
    if mod.__name__.endswith("fresing_render"):
        addon_utils.enable(mod.__name__, default_set=True)
        importlib.import_module(mod.__name__ + ".selftest").main()
        break
else:
    print("Fresing Render is not installed in this Blender")
"@ | Set-Content -Path $Launcher -Encoding UTF8

$Shell = New-Object -ComObject WScript.Shell
function MakeShortcut($path, $arguments, $description) {
    $lnk = $Shell.CreateShortcut($path)
    $lnk.TargetPath = $BlenderExe
    $lnk.Arguments = $arguments
    $lnk.WorkingDirectory = $BlenderDir
    $lnk.IconLocation = "$BlenderExe,0"
    $lnk.Description = $description
    $lnk.Save()
}
$Desktop = [Environment]::GetFolderPath("Desktop")
$StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Fresing Render"
New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null

Step "Creating shortcuts"
MakeShortcut (Join-Path $Desktop "Fresing Render.lnk") "--app-template fresing_render" "Render STEP models"
MakeShortcut (Join-Path $StartMenu "Fresing Render.lnk") "--app-template fresing_render" "Render STEP models"
MakeShortcut (Join-Path $StartMenu "Fresing Render - Self test.lnk") "--background --python `"$Launcher`"" "Check this PC and write a report on the Desktop"

Set-Content -Path (Join-Path $InstallDir "installed.txt") -Value "Fresing Render installed $(Get-Date -Format s)`r`nBlender $BlenderVersion`r`nUpdate URL: $UpdateUrl"

Write-Host ""
Write-Host "Done. Start 'Fresing Render' from the Desktop." -ForegroundColor Green
Write-Host "Tip: run 'Fresing Render - Self test' from the Start menu once; it writes a report on the Desktop."
