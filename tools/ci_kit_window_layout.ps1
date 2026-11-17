<#
.SYNOPSIS
  Layout check of the render kit's windows (task 0177): every text fits its control, nothing overlaps, everything lies
  inside its window, and the start window fits the screen (its middle scrolls, the buttons stay visible).

.DESCRIPTION
  Runs in Windows PowerShell 5.1 (what the kit uses), started by tools/ci_windows_install.ps1 once per display scale.
  Loads site/render_kit/kit_window.ps1 with -Mode layout -TestScale <scale> -TestScreen <screen>: the fonts and
  distances are those of that display scale on GitHub's 96-DPI screen. Builds the start window (with and without
  "Continue the run"), the status window with its longest texts and the end countdown, shows each for a moment at the
  top left of the screen, checks it, and saves a picture of it (DrawToBitmap) as <OutDir>\kit_<scale>_<window>.png.
  Prints "LAYOUT OK ..." or one "LAYOUT PROBLEM ..." line per fault (the control, its text, what is wrong); exit 1 then.

.EXAMPLE
  powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File tools\ci_kit_window_layout.ps1 -Scale 1.5 -Screen 1366x768 -OutDir out
#>
param(
    [double]$Scale = 1.0,
    [string]$Screen = "1920x1080",
    [string]$OutDir = "."
)
$ErrorActionPreference = "Stop"
$KitDir = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\site\render_kit")).Path
. (Join-Path $KitDir "kit_window.ps1") -Mode layout -TestScale $Scale -TestScreen $Screen
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# GitHub's Windows machine has a small screen: a window bigger than the screen is cut to it by Windows. Switch to the
# test screen's size for this process only (CDS_FULLSCREEN: Windows puts the old size back when the process ends).
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class FresingScreen {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    public struct DEVMODE {
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string dmDeviceName;
        public short dmSpecVersion; public short dmDriverVersion; public short dmSize; public short dmDriverExtra;
        public int dmFields; public int dmPositionX; public int dmPositionY; public int dmDisplayOrientation;
        public int dmDisplayFixedOutput; public short dmColor; public short dmDuplex; public short dmYResolution;
        public short dmTTOption; public short dmCollate;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string dmFormName;
        public short dmLogPixels; public int dmBitsPerPel; public int dmPelsWidth; public int dmPelsHeight;
        public int dmDisplayFlags; public int dmDisplayFrequency; public int dmICMMethod; public int dmICMIntent;
        public int dmMediaType; public int dmDitherType; public int dmReserved1; public int dmReserved2;
        public int dmPanningWidth; public int dmPanningHeight;
    }
    [DllImport("user32.dll", CharSet = CharSet.Auto)] static extern int EnumDisplaySettings(string dev, int mode, ref DEVMODE dm);
    [DllImport("user32.dll", CharSet = CharSet.Auto)] static extern int ChangeDisplaySettings(ref DEVMODE dm, int flags);
    public static int Set(int w, int h) {
        DEVMODE dm = new DEVMODE();
        dm.dmSize = (short)Marshal.SizeOf(typeof(DEVMODE));
        if (EnumDisplaySettings(null, -1, ref dm) == 0) return -100;
        dm.dmPelsWidth = w; dm.dmPelsHeight = h; dm.dmFields = 0x80000 | 0x100000;
        return ChangeDisplaySettings(ref dm, 4);
    }
}
"@
$was = [System.Windows.Forms.SystemInformation]::PrimaryMonitorSize
if ($Screen -match '^(\d+)x(\d+)$' -and ($was.Width -lt [int]$Matches[1] -or $was.Height -lt [int]$Matches[2])) {
    $r = [FresingScreen]::Set([int]$Matches[1], [int]$Matches[2])
    Write-Host ("   screen {0}x{1} -> {2} (ChangeDisplaySettings {3})" -f $was.Width, $was.Height,
        [System.Windows.Forms.SystemInformation]::PrimaryMonitorSize, $r)
}

$Problems = [System.Collections.ArrayList]::new()
$Tag = "{0:0.00}x {1}" -f $Scale, $Screen

function Bad([string]$Where, $C, [string]$Why) {
    $name = $C.GetType().Name
    [void]$Problems.Add(("LAYOUT PROBLEM {0} {1}: {2} '{3}' {4}" -f $Tag, $Where, $name, $C.Text, $Why))
}

function Test-TextFits([string]$Where, $C) {
    $f = $C.Font
    $cw = $C.ClientSize.Width
    $ch = $C.ClientSize.Height
    $arrow = Get-ArrowWidth
    if ($C -is [System.Windows.Forms.Label]) {
        $m = Measure-UiText $C.Text $f $cw
        if ($m.Width -gt $cw -or $m.Height -gt $ch) { Bad $Where $C "needs $($m.Width) x $($m.Height), has $cw x $ch" }
    } elseif ($C -is [System.Windows.Forms.CheckBox] -or $C -is [System.Windows.Forms.RadioButton]) {
        $m = Measure-UiText $C.Text $f
        $need = $m.Width + (Px 18)
        if ($need -gt $cw -or $m.Height -gt $ch) { Bad $Where $C "needs $need x $($m.Height) with its box, has $cw x $ch" }
    } elseif ($C -is [System.Windows.Forms.Button]) {
        foreach ($t in (Get-FitTexts $C)) {
            $m = Measure-UiText $t $f
            if ($m.Width + (Px 10) -gt $cw -or $m.Height -gt $ch) { Bad $Where $C "text '$t' needs $($m.Width) x $($m.Height), has $cw x $ch" }
        }
    } elseif ($C -is [System.Windows.Forms.ComboBox]) {
        foreach ($t in $C.Items) {
            $m = Measure-UiText ([string]$t) $f
            if ($m.Width + $arrow + (Px 4) -gt $C.Width) { Bad $Where $C "item '$t' needs $($m.Width) + the arrow, has $($C.Width)" }
        }
    } elseif ($C -is [System.Windows.Forms.DateTimePicker]) {
        $m = Measure-UiText "23:59" $f
        if ($m.Width + $arrow + (Px 4) -gt $C.Width) { Bad $Where $C "a time needs $($m.Width) + the spin buttons, has $($C.Width)" }
        if ($C.Height -lt $C.PreferredHeight) { Bad $Where $C "is $($C.Height) high, needs $($C.PreferredHeight)" }
    } elseif ($C -is [System.Windows.Forms.NumericUpDown]) {
        $m = Measure-UiText "100" $f
        if ($m.Width + $arrow + (Px 4) -gt $C.Width) { Bad $Where $C "'100' needs $($m.Width) + the spin buttons, has $($C.Width)" }
        if ($C.Height -lt $C.PreferredHeight) { Bad $Where $C "is $($C.Height) high, needs $($C.PreferredHeight)" }
    } elseif ($C -is [System.Windows.Forms.ListView]) {
        $sum = 0
        foreach ($col in $C.Columns) {
            $sum += $col.Width
            $m = Measure-UiText $col.Text $f
            if ($m.Width + (Px 8) -gt $col.Width) { Bad $Where $C "column '$($col.Text)' is $($col.Width) wide, its title needs $($m.Width)" }
        }
        if ($sum -gt $cw) { Bad $Where $C "columns are $sum wide, the list shows $cw (a sideways scroll bar)" }
        foreach ($it in $C.Items) {
            $m0 = Measure-UiText $it.Text $f
            if ($m0.Width + (Px 30) -gt $C.Columns[0].Width) { Bad $Where $C "model '$($it.Text)' needs $($m0.Width) + its box, column is $($C.Columns[0].Width)" }
            $t1 = $it.SubItems[1].Text
            $m1 = Measure-UiText $t1 $f
            if ($m1.Width + (Px 8) -gt $C.Columns[1].Width) { Bad $Where $C "time '$t1' needs $($m1.Width), column is $($C.Columns[1].Width)" }
            $r = $C.GetItemRect($it.Index)
            if ($r.Bottom -gt $ch) { Bad $Where $C "model '$($it.Text)' is below the list's bottom ($($r.Bottom) > $ch)" }
        }
    }
}

function Test-Children([string]$Where, $Parent, [int]$LimitW, [int]$LimitH) {
    $kids = @($Parent.Controls | Where-Object { $_.Visible })
    foreach ($c in $kids) {
        $b = $c.Bounds
        if ($b.Left -lt 0 -or $b.Top -lt 0 -or $b.Right -gt $LimitW -or $b.Bottom -gt $LimitH) {
            Bad $Where $c ("at {0},{1} {2}x{3} is outside its area {4}x{5}" -f $b.Left, $b.Top, $b.Width, $b.Height, $LimitW, $LimitH)
        }
        if ($b.Width -le 0 -or $b.Height -le 0) { Bad $Where $c "has no size" }
        Test-TextFits $Where $c
        if ($c -is [System.Windows.Forms.Panel]) {
            $lh = $c.ClientSize.Height
            if ($c.AutoScroll) { $lh = [math]::Max($lh, $c.DisplayRectangle.Height) }
            Test-Children ($Where + "/" + $c.GetType().Name + "@" + $b.Top) $c $c.ClientSize.Width $lh
        }
    }
    for ($i = 0; $i -lt $kids.Count; $i++) {
        for ($j = $i + 1; $j -lt $kids.Count; $j++) {
            if ($kids[$i].Bounds.IntersectsWith($kids[$j].Bounds)) {
                Bad $Where $kids[$i] ("overlaps {0} '{1}'" -f $kids[$j].GetType().Name, $kids[$j].Text)
            }
        }
    }
}

function Test-Window([string]$Name, $U) {
    $form = $U.form
    $WantW = $form.Tag.Width
    $WantH = $form.Tag.Height
    $form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
    $form.Location = New-Object System.Drawing.Point(0, 0)
    $form.ShowInTaskbar = $false
    $form.Show()
    [System.Windows.Forms.Application]::DoEvents()
    $where = $Name
    if ($form.ClientSize.Width -ne $WantW -or $form.ClientSize.Height -ne $WantH) {
        [void]$Problems.Add(("LAYOUT PROBLEM {0} {1}: the window is {2}x{3} instead of {4}x{5} (this test screen is too small to show it: {6})" -f
            $Tag, $Name, $form.ClientSize.Width, $form.ClientSize.Height, $WantW, $WantH,
            [System.Windows.Forms.SystemInformation]::MaxWindowTrackSize))
    }
    $wa = Get-WorkArea
    $outer = $form.ClientSize.Height + (Get-FrameHeight $form)
    if ($outer -gt $wa.Height) {
        [void]$Problems.Add(("LAYOUT PROBLEM {0} {1}: the window is {2} high with its title bar, the screen has {3}" -f $Tag, $Name, $outer, $wa.Height))
    }
    if ($form.ClientSize.Width -gt $wa.Width) {
        [void]$Problems.Add(("LAYOUT PROBLEM {0} {1}: the window is {2} wide, the screen has {3}" -f $Tag, $Name, $form.ClientSize.Width, $wa.Width))
    }
    Test-Children $where $form $form.ClientSize.Width $form.ClientSize.Height
    $file = Join-Path $OutDir ("kit_{0:0.00}_{1}_{2}.png" -f $Scale, ($Screen -replace "x", "-"), $Name)
    $bmp = New-Object System.Drawing.Bitmap($form.Width, $form.Height)
    $form.DrawToBitmap($bmp, (New-Object System.Drawing.Rectangle(0, 0, $form.Width, $form.Height)))
    $bmp.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    if ($U.body -and $U.body.AutoScroll) {                 # the lower part of a scrolling start window
        $U.body.AutoScrollPosition = New-Object System.Drawing.Point(0, 100000)
        [System.Windows.Forms.Application]::DoEvents()
        $bmp = New-Object System.Drawing.Bitmap($form.Width, $form.Height)
        $form.DrawToBitmap($bmp, (New-Object System.Drawing.Rectangle(0, 0, $form.Width, $form.Height)))
        $bmp.Save(($file -replace "\.png$", "_scrolled.png"), [System.Drawing.Imaging.ImageFormat]::Png)
        $bmp.Dispose()
    }
    Write-Host ("   {0} {1}: {2} x {3} px{4}" -f $Tag, $Name, $form.ClientSize.Width, $form.ClientSize.Height,
        $(if ($U.body -and $U.body.AutoScroll) { ", the middle scrolls" } else { "" }))
    $form.Close()
    $form.Dispose()
}

# ---- the check itself: a cut text, an overlap and a control outside its window must be found ----
$probe = New-Form "probe"
$probe.W = Px 300
$pa = New-Text "A label much too long for its little box"
$pa.SetBounds((Px 10), (Px 80), (Px 40), (Px 10))
$pb = New-Text "x"
$pb.SetBounds((Px 20), (Px 84), (Px 40), (Px 20))
$pc = New-Button "Out"
$pc.SetBounds((Px 260), (Px 120), (Px 100), (Px 30))
$probe.form.Controls.AddRange(@($pa, $pb, $pc))
[void](Set-Head $probe)
Set-ClientSize $probe.form (Px 300) (Px 200)
$probe.form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
$probe.form.ShowInTaskbar = $false
$probe.form.Show()
[System.Windows.Forms.Application]::DoEvents()
$before = $Problems.Count
Test-Children "probe" $probe.form $probe.form.ClientSize.Width $probe.form.ClientSize.Height
$probe.form.Close()
$found = @($Problems | Select-Object -Skip $before)
if ($found.Count) { $Problems.RemoveRange($before, $found.Count) }
foreach ($k in @("needs", "overlaps", "outside")) {
    if (-not ($found | Where-Object { $_ -like "*$k*" })) { [void]$Problems.Add("LAYOUT PROBLEM $Tag the check itself finds no control that $k (found: $($found -join ' / '))") }
}

# ---- sample data: the kit's own model titles, long times, a missing file, a run to continue ----
$titles = @(Get-Content -LiteralPath (Join-Path $KitDir "models.ini") | Where-Object { $_ -match '^title\s*=' } |
    ForEach-Object { ($_ -split "=", 2)[1].Trim() })
$models = @()
$k = 0
foreach ($t in $titles) {
    $k += 1
    $models += [pscustomobject]@{ id = "m$k"; title = $t; gpu = (4000.0 * $k + 1234); cpu = 900.0; found = ($k -ne 4) }
}
$models += [pscustomobject]@{ id = "long"; title = "A model with a long name for the test (88 h)"; gpu = 316000.0; cpu = 5000.0; found = $true }
$std = [pscustomobject]@{ load = 70; max_temp = 80; quiet_on = $true; quiet_start = "22:00"; quiet_end = "07:00";
    quiet_load = 60; quiet_max_temp = 75; when_done = "shutdown" }
$resume = [pscustomobject]@{ text = "Continue the run of 2026-11-15 23:10 (128 of 134 done)"; gpu = 9000.0; cpu = 600.0;
    done = 128; total = 134 }

foreach ($withResume in @($true, $false)) {
    $est = [pscustomobject]@{ standard = $std; factory = $std; resume = $(if ($withResume) { $resume } else { $null });
        models = $models; standard_file = "" }
    $u = Build-StartWindow $est
    $u.loadText.Text = "100 %"
    $u.expected.Text = $ExpectedLongest
    Set-TempBox $u.maxTemp 85
    Set-TempBox $u.qTemp 85
    $u.done.SelectedIndex = 2
    $name = $(if ($withResume) { "start_continue" } else { "start" })
    Test-Window $name $u
}

# ---- the start window still does what it did (task 0144): untick a model, start at a time, Back to standard ----
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("kit_layout_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$factory = [pscustomobject]@{ load = 100; max_temp = 0; quiet_on = $false; quiet_start = "22:00"; quiet_end = "07:00";
    quiet_load = 60; quiet_max_temp = 0; when_done = "nothing" }
$est = [pscustomobject]@{ standard = $std; factory = $factory; resume = $null; models = $models;
    standard_file = (Join-Path $tmp "std\site_kit.json") }
$Estimate = Join-Path $tmp "estimate.json"
$Choices = Join-Path $tmp "run_choices.json"
Write-Utf8 $Estimate (ConvertTo-Json -InputObject $est -Depth 5)
$script:seen = @{}
$TestOnShown = {                                        # runs inside Show-StartWindow: its controls are in scope
    $script:seen.loadBefore = $load.Value
    $script:seen.expected = $expected.Text
    $back.PerformClick()
    $script:seen.loadBack = $load.Value
    $script:seen.quietBack = $quiet.Checked
    $load.Value = 75
    $list.Items[1].Checked = $false
    $at.Checked = $true
    $atTime.Value = [datetime]::Today.AddHours(2).AddMinutes(15)
    $done.SelectedIndex = 1
    $start.PerformClick()
}
$rc = @(Show-StartWindow)[-1]
$TestOnShown = $null
$want = @($models | Where-Object { $_.found } | ForEach-Object { $_.id } | Where-Object { $_ -ne "m2" })
try {
    $ch = Get-Content -LiteralPath $Choices -Raw | ConvertFrom-Json
    $sf = Get-Content -LiteralPath $est.standard_file -Raw | ConvertFrom-Json
    $why = @()
    if ($rc -ne 0) { $why += "returned $rc, not 0" }
    if ($script:seen.loadBefore -ne 70) { $why += "the standard's load 70 was shown as $($script:seen.loadBefore)" }
    if ($script:seen.expected -notlike "Expected: about *") { $why += "expected time '$($script:seen.expected)'" }
    if ($script:seen.loadBack -ne 100 -or $script:seen.quietBack) { $why += "Back to standard gave load $($script:seen.loadBack), quiet $($script:seen.quietBack)" }
    if ((@($ch.models) -join ",") -ne ($want -join ",")) { $why += "models $(@($ch.models) -join ',') instead of $($want -join ',')" }
    if ($ch.load -ne 75 -or $ch.start_at -ne "02:15" -or $ch.when_done -ne "sleep" -or $ch.resume -or $ch.quiet_on) {
        $why += "choices $(ConvertTo-Json -InputObject $ch -Compress)"
    }
    if ($sf.load -ne 75 -or $sf.when_done -ne "sleep" -or $sf.PSObject.Properties.Name -contains "models") {
        $why += "standard $(ConvertTo-Json -InputObject $sf -Compress)"
    }
    foreach ($w in $why) { [void]$Problems.Add("LAYOUT PROBLEM $Tag start window clicked through: $w") }
} catch {
    [void]$Problems.Add("LAYOUT PROBLEM $Tag start window clicked through: no choices written ($($_.Exception.Message))")
}
Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
if (-not $Problems.Count) { Write-Host "   $Tag start window clicked through: choices and standard as asked" }

$texts = @(
    @("Waiting to start", "Starts at 02:15", "load 60 %"),
    @("Model 8 of 8: IEA 15 MW offshore wind turbine", "Picture 2 of 2 (ISO_LEFT)",
      "100 % done   |   load 100 %   |   85 $Deg" + "C   |   done at about Wed 23:58"),
    @("Waiting for the graphics card to cool down", "Importing and setting up", "45 % done   |   load 60 %"),
    @("The run has stopped (its black window was closed?)", "Double-click the kit again and tick Continue to make the rest.", ""),
    @("Pausing - after the picture being made", "Stopped with a problem: see log.txt", "")
)
$n = 0
foreach ($t in $texts) {
    $n += 1
    $u = Build-StatusWindow
    $u.line1.Text = $t[0]
    $u.line2.Text = $t[1]
    $u.line3.Text = $t[2]
    if ($n -eq 2) { $u.pause.Text = "Resume" }
    Set-StatusLayout $u
    Test-Window ("status$n") $u
}

foreach ($verb in @("go to sleep", "shut down (programs with unsaved work are closed)")) {
    $u = Build-EndWindow $verb
    $u.msg.Text = "The pictures are done. The PC will $verb in 60 s."
    Test-Window ("end_" + $verb.Split(" ")[0]) $u
}

if ($Problems.Count) {
    $Problems | ForEach-Object { Write-Host $_ }
    exit 1
}
Write-Host "LAYOUT OK $Tag"
exit 0
