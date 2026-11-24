<#
.SYNOPSIS
  Removes Fresing Render (its Blender, settings and shortcuts). Projects and renders are kept.

.DESCRIPTION
  Started by Uninstall.bat next to the installer, or from Settings > Apps > Installed apps (task 0265): the entry's
  Uninstall runs the copy in the install's Tools folder with -Pause. That copy lives in the folder it removes, so it
  first starts a copy of itself in %TEMP% and waits for it. The entry in Installed apps goes last, and only when the
  folder is gone.
#>
param([string]$InstallDir = (Join-Path $env:LOCALAPPDATA "FresingRender"), [switch]$Pause, [switch]$FromTemp)

$InstallDir = [IO.Path]::GetFullPath($InstallDir.TrimEnd('\', '/'))
$AppsKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\FresingRender"

function Finish([int]$code) {
    if ($Pause) {
        Write-Host ""
        Write-Host "Press any key to close this window..."
        try { [void][Console]::ReadKey($true) } catch { Start-Sleep -Seconds 5 }
    }
    exit $code
}

# Never run from inside the folder that is removed (the temp copy would hold it too)
try { Set-Location -LiteralPath ([IO.Path]::GetTempPath()) } catch { }
# Only an install made by Install.bat is removed (a wrong -InstallDir must never delete another folder)
if (-not (Test-Path -LiteralPath (Join-Path $InstallDir "installed.txt"))) {
    Write-Host "No Fresing Render installation found in $InstallDir (installed.txt is missing). Nothing was removed." -ForegroundColor Yellow
    Finish 1
}

# Inside the folder it removes: run a copy from %TEMP% (a running script's folder cannot be deleted from under it)
$me = $MyInvocation.MyCommand.Path
if (-not $FromTemp -and $me -and $me.StartsWith("$InstallDir\", [StringComparison]::OrdinalIgnoreCase)) {
    $copy = Join-Path ([IO.Path]::GetTempPath()) ("Uninstall-FresingRender-" + [guid]::NewGuid().ToString("N") + ".ps1")
    Copy-Item -LiteralPath $me -Destination $copy -Force
    $argList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $copy, "-InstallDir", $InstallDir, "-FromTemp")
    if ($Pause) { $argList += "-Pause" }
    & powershell.exe @argList
    $code = $LASTEXITCODE
    Remove-Item -LiteralPath $copy -Force -ErrorAction SilentlyContinue
    exit $code
}

Write-Host "Removing Fresing Render from $InstallDir" -ForegroundColor Cyan
Write-Host "Your projects (.blend files), renders and backups are kept."

$running = Get-Process -Name blender, blender-launcher, "Fresing Render" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path.StartsWith("$InstallDir\", [StringComparison]::OrdinalIgnoreCase) }
if ($running) {
    Write-Host "Fresing Render is still open. Close it first, then run Uninstall again." -ForegroundColor Yellow
    Finish 1
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$Programs = [Environment]::GetFolderPath("Programs")
# task 0212: "Fresing Render" on the Desktop and in the Start menu (the Tools folder goes with the install folder),
# and what installs before 0212 made: two more on the Desktop and the Start-menu folder "Fresing Render"
foreach ($n in @("Fresing Render.lnk", "Fresing Render - PC check.lnk", "Fresing Render - PC check (heavy).lnk")) {
    Remove-Item -LiteralPath (Join-Path $Desktop $n) -Force -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath (Join-Path $Programs "Fresing Render.lnk") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $Programs "Fresing Render") -Recurse -Force -ErrorAction SilentlyContinue
# task 0217: the app's own folder in the Toolbox folder (only that one; never through a link or junction)
$ToolboxHome = if ($env:TOOLBOX_HOME) { $env:TOOLBOX_HOME } elseif ($env:USERPROFILE) { Join-Path $env:USERPROFILE "Toolbox" } else { "" }
if ($ToolboxHome -and [IO.Path]::IsPathRooted($ToolboxHome)) {
    $ToolboxMine = Join-Path (Join-Path $ToolboxHome "tools") "nl.fresing.render"
    $linked = $false
    foreach ($p in @($ToolboxHome, (Join-Path $ToolboxHome "tools"), $ToolboxMine)) {
        $item = Get-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue
        if ($item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { $linked = $true }
    }
    if ((Test-Path -LiteralPath $ToolboxMine -PathType Container) -and -not $linked) {
        try {
            # links and junctions inside go first, one by one and deepest first, as links only (never followed)
            Get-ChildItem -LiteralPath $ToolboxMine -Recurse -Force -Attributes ReparsePoint -ErrorAction SilentlyContinue |
                Sort-Object { $_.FullName.Length } -Descending | ForEach-Object {
                    if ($_.PSIsContainer) { [IO.Directory]::Delete($_.FullName) } else { [IO.File]::Delete($_.FullName) }
                }
            [IO.Directory]::Delete($ToolboxMine, $true)
        } catch {
            Write-Host "   (Fresing Render's part of the Toolbox folder could not be removed - in use or read-only: delete $ToolboxMine by hand)"
        }
    }
}
if (Test-Path -LiteralPath $InstallDir) {
    Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
}
if (Test-Path -LiteralPath $InstallDir) {
    # the uninstaller itself may be gone by now: put it back, so Uninstall in Settings still works for the second try
    if ($FromTemp -and $me) {
        $back = Join-Path $InstallDir "Tools"
        try { New-Item -ItemType Directory -Force -Path $back | Out-Null; Copy-Item -LiteralPath $me -Destination (Join-Path $back "Uninstall-FresingRender.ps1") -Force } catch { }
    }
    Write-Host "Some files in $InstallDir could not be removed (in use?). Restart the PC and run Uninstall again." -ForegroundColor Yellow
    Finish 1
}
# task 0296: Windows' graphics preference of the programs that were in this folder (the installer and the app set it)
try {
    $GpuKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Software\Microsoft\DirectX\UserGpuPreferences", $true)
    if ($GpuKey) {
        try {
            foreach ($name in $GpuKey.GetValueNames()) {
                if ($name.StartsWith("$InstallDir\", [StringComparison]::OrdinalIgnoreCase)) { $GpuKey.DeleteValue($name, $false) }
            }
        } finally { $GpuKey.Close() }
    }
} catch { }
# the entry in Settings > Apps > Installed apps goes last, and only the one that belongs to this folder
try {
    $entry = Get-ItemProperty -LiteralPath $AppsKey -ErrorAction Stop
    $where = [string]$entry.InstallLocation
    if ($where -and ([IO.Path]::GetFullPath($where.TrimEnd('\', '/')) -ieq $InstallDir)) {
        Remove-Item -LiteralPath $AppsKey -Force -ErrorAction SilentlyContinue
    }
} catch { }
Write-Host "Fresing Render removed. Your .blend projects and renders were not touched." -ForegroundColor Green
Finish 0
