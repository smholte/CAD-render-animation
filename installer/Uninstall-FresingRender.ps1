<#
.SYNOPSIS
  Removes Fresing Render (its Blender, settings and shortcuts). Projects and renders are kept.
#>
param([string]$InstallDir = (Join-Path $env:LOCALAPPDATA "FresingRender"))

$ErrorActionPreference = "Continue"
$Desktop = [Environment]::GetFolderPath("Desktop")
$StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Fresing Render"

Remove-Item (Join-Path $Desktop "Fresing Render.lnk") -Force -ErrorAction SilentlyContinue
Remove-Item $StartMenu -Recurse -Force -ErrorAction SilentlyContinue
if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
}
Write-Host "Fresing Render removed. Your .blend projects and renders were not touched." -ForegroundColor Green
