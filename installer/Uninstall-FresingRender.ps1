<#
.SYNOPSIS
  Removes Fresing Render (its Blender, settings and shortcuts). Projects and renders are kept.
#>
param([string]$InstallDir = (Join-Path $env:LOCALAPPDATA "FresingRender"))

$running = Get-Process -Name blender, blender-launcher, "Fresing Render" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path.StartsWith($InstallDir, [StringComparison]::OrdinalIgnoreCase) }
if ($running) {
    Write-Host "Fresing Render is still open. Close it first, then run Uninstall again." -ForegroundColor Yellow
    exit 1
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
if (Test-Path -LiteralPath $InstallDir) {
    Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
}
if (Test-Path -LiteralPath $InstallDir) {
    Write-Host "Some files in $InstallDir could not be removed (in use?). Restart the PC and run Uninstall again." -ForegroundColor Yellow
    exit 1
}
Write-Host "Fresing Render removed. Your .blend projects and renders were not touched." -ForegroundColor Green
