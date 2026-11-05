<#
.SYNOPSIS
  Removes Fresing Render (its Blender, settings and shortcuts). Projects and renders are kept.
#>
param([string]$InstallDir = (Join-Path $env:LOCALAPPDATA "FresingRender"))

$running = Get-Process -Name blender, blender-launcher -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path.StartsWith($InstallDir, [StringComparison]::OrdinalIgnoreCase) }
if ($running) {
    Write-Host "Fresing Render is still open. Close it first, then run Uninstall again." -ForegroundColor Yellow
    exit 1
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Fresing Render"
Remove-Item -LiteralPath (Join-Path $Desktop "Fresing Render.lnk") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $Desktop "Fresing Render - PC check.lnk") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $StartMenu -Recurse -Force -ErrorAction SilentlyContinue
if (Test-Path -LiteralPath $InstallDir) {
    Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
}
if (Test-Path -LiteralPath $InstallDir) {
    Write-Host "Some files in $InstallDir could not be removed (in use?). Restart the PC and run Uninstall again." -ForegroundColor Yellow
    exit 1
}
Write-Host "Fresing Render removed. Your .blend projects and renders were not touched." -ForegroundColor Green
