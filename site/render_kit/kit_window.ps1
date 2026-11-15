<#
  Fresing site kit - the start window, the status window and the end countdown (task 0144).

  Started by "Make site pictures.bat" with Windows PowerShell 5.1 (part of Windows; nothing to install):
    -Mode start  -Estimate <estimate.json> -Choices <run_choices.json>
        The start window: graphics-card load, max temperature, quiet hours, models, start time, when done, continue a
        stopped run. Writes the choices for make_site_pictures.py (--choices=) and keeps them as the standard in
        %LOCALAPPDATA%\Fresing Render\site_kit.json (outside the kit, so a new kit keeps them).
        Exit 0 = Start, 1 = Cancel. Anything else: the .bat asks in the console instead.
    -Mode status -Out <output folder>
        The small status window: reads output\status.json every 2 s, writes pause / run / stop to output\control.txt.
        Closes itself when the .bat writes "ended" there.
    -Mode end    -Choices <run_choices.json> -Code <exit code of the run>
        When done = sleep or shut down: a 60-second countdown with Cancel, then does it (no admin rights needed).
    -Mode lib    only defines the functions (the tests).

  This file must stay plain ASCII (Windows PowerShell 5.1 reads a file without a BOM as ANSI) with CRLF line ends.
  Get-WallSeconds is the same loop as kit_run.wall_seconds (a test compares them).
#>
param(
    [string]$Mode = "start",
    [string]$Estimate = "",
    [string]$Choices = "",
    [string]$Out = "",
    [int]$Code = 0
)

$ErrorActionPreference = "Stop"
$Deg = [string][char]0x00B0
$StepSeconds = 300.0

function Get-ClockMinutes([string]$Clock) {
    $p = $Clock.Split(":")
    return ([int]$p[0]) * 60 + [int]$p[1]
}

function Test-Quiet([datetime]$When, [bool]$QuietOn, [string]$QuietStart, [string]$QuietEnd) {
    if (-not $QuietOn) { return $false }
    $now = $When.Hour * 60 + $When.Minute
    $a = Get-ClockMinutes $QuietStart
    $b = Get-ClockMinutes $QuietEnd
    if ($a -eq $b) { return $false }
    if ($a -lt $b) { return ($now -ge $a -and $now -lt $b) }
    return ($now -ge $a -or $now -lt $b)
}

function Get-WallSeconds([double]$Gpu, [double]$Cpu, [datetime]$Start, [int]$Load, [bool]$QuietOn,
                         [string]$QuietStart, [string]$QuietEnd, [int]$QuietLoad) {
    $total = $Gpu + $Cpu
    if ($total -le 0) { return 0.0 }
    $gshare = $Gpu / $total
    $left = $total
    $t = 0.0
    for ($i = 0; $i -lt 100000; $i++) {
        $l = $Load
        if (Test-Quiet $Start.AddSeconds($t) $QuietOn $QuietStart $QuietEnd) { $l = $QuietLoad }
        $stretch = (1.0 - $gshare) + $gshare * 100.0 / $l
        $work = $StepSeconds / $stretch
        if ($work -ge $left) { return $t + $left * $stretch }
        $left -= $work
        $t += $StepSeconds
    }
    return $t
}

function Format-Duration([double]$Seconds) {
    $m = [int][math]::Round($Seconds / 60.0)
    if ($m -ge 60) { return ("{0} h {1:00} min" -f [math]::Floor($m / 60), ($m % 60)) }
    return ("{0} min" -f [math]::Max(1, $m))
}

function Write-Utf8([string]$Path, [string]$Text) {
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

if ($Mode -eq "lib") { return }

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
try {
    Add-Type -Namespace FresingKit -Name Dpi -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
    [void][FresingKit.Dpi]::SetProcessDPIAware()
} catch { }
[System.Windows.Forms.Application]::EnableVisualStyles()

function New-Color([string]$Hex) { return [System.Drawing.ColorTranslator]::FromHtml($Hex) }
$Green = New-Color "#479B29"
$GreenDark = New-Color "#2F6A1B"
$Charcoal = New-Color "#252E36"
$Slate = New-Color "#5B6670"
$Mist = New-Color "#F1F3F5"
$Deep = New-Color "#1A2027"
$Font = New-Object System.Drawing.Font("Segoe UI", 9.75)
$Bold = New-Object System.Drawing.Font("Segoe UI", 9.75, [System.Drawing.FontStyle]::Bold)
$Small = New-Object System.Drawing.Font("Segoe UI", 8.5)

function New-Form([string]$Title, [int]$W, [int]$H) {
    $f = New-Object System.Windows.Forms.Form
    $f.Text = $Title
    $f.AutoScaleDimensions = New-Object System.Drawing.SizeF(96, 96)
    $f.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::Dpi
    $f.ClientSize = New-Object System.Drawing.Size($W, $H)
    $f.Font = $Font
    $f.BackColor = $Mist
    $f.ForeColor = $Charcoal
    $f.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
    $f.MaximizeBox = $false
    $f.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
    $head = New-Object System.Windows.Forms.Panel
    $head.BackColor = $Deep
    $head.SetBounds(0, 0, $W, 64)
    $logo = Join-Path $PSScriptRoot "fresing_logo.png"
    if (Test-Path -LiteralPath $logo) {
        $pic = New-Object System.Windows.Forms.PictureBox
        $pic.SizeMode = [System.Windows.Forms.PictureBoxSizeMode]::Zoom
        $pic.Image = [System.Drawing.Image]::FromFile($logo)
        $pic.SetBounds(16, 10, 152, 44)
        $head.Controls.Add($pic)
    }
    $t = New-Object System.Windows.Forms.Label
    $t.Text = "Site pictures"
    $t.ForeColor = [System.Drawing.Color]::White
    $t.Font = New-Object System.Drawing.Font("Segoe UI", 12)
    $t.TextAlign = [System.Drawing.ContentAlignment]::MiddleRight
    $t.SetBounds($W - 216, 16, 200, 32)
    $head.Controls.Add($t)
    $f.Controls.Add($head)
    return $f
}

function Add-Label($Parent, [string]$Text, [int]$X, [int]$Y, [int]$W, [int]$H = 20, $LabelFont = $null, $Color = $null) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $Text
    $l.SetBounds($X, $Y, $W, $H)
    if ($LabelFont) { $l.Font = $LabelFont }
    if ($Color) { $l.ForeColor = $Color }
    $Parent.Controls.Add($l)
    return $l
}

function New-Button([string]$Text, [int]$X, [int]$Y, [int]$W, [bool]$Primary = $false) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $Text
    $b.SetBounds($X, $Y, $W, 30)
    if ($Primary) {
        $b.BackColor = $Green
        $b.ForeColor = [System.Drawing.Color]::White
        $b.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
        $b.FlatAppearance.BorderColor = $GreenDark
        $b.Font = $Bold
    } else {
        $b.BackColor = [System.Drawing.Color]::White
    }
    return $b
}

function New-TempBox([int]$X, [int]$Y) {
    $c = New-Object System.Windows.Forms.ComboBox
    $c.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
    [void]$c.Items.Add("Off")
    for ($t = 70; $t -le 85; $t++) { [void]$c.Items.Add("$t $Deg" + "C") }
    $c.SetBounds($X, $Y, 80, 24)
    return $c
}

function Set-TempBox($Box, [int]$Value) {
    if ($Value -ge 70 -and $Value -le 85) { $Box.SelectedIndex = $Value - 69 } else { $Box.SelectedIndex = 0 }
}

function Get-TempBox($Box) {
    if ($Box.SelectedIndex -le 0) { return 0 }
    return 69 + $Box.SelectedIndex
}

function New-ClockPicker([int]$X, [int]$Y, [string]$Clock) {
    $d = New-Object System.Windows.Forms.DateTimePicker
    $d.Format = [System.Windows.Forms.DateTimePickerFormat]::Custom
    $d.CustomFormat = "HH:mm"
    $d.ShowUpDown = $true
    $d.SetBounds($X, $Y, 70, 24)
    $d.Value = [datetime]::Today.AddMinutes((Get-ClockMinutes $Clock))
    return $d
}

# ---------------------------------------------------------------------------------------------------------------
# the start window
# ---------------------------------------------------------------------------------------------------------------
function Show-StartWindow {
    $est = Get-Content -LiteralPath $Estimate -Raw | ConvertFrom-Json
    $std = $est.standard
    $factory = $est.factory
    $resume = $est.resume
    $models = @($est.models)

    $W = 580
    $form = New-Form "Fresing site pictures - start" $W 700
    $y = 76

    $resumeBox = $null
    if ($resume) {
        $resumeBox = New-Object System.Windows.Forms.CheckBox
        $resumeBox.Text = [string]$resume.text
        $resumeBox.Font = $Bold
        $resumeBox.Checked = $true
        $resumeBox.SetBounds(16, $y, $W - 32, 24)
        $form.Controls.Add($resumeBox)
        $y += 26
        [void](Add-Label $form "Makes only the pictures and clips that are not done yet. Untick it to start a new run." 34 $y ($W - 50) 18 $Small $Slate)
        $y += 26
    }

    [void](Add-Label $form "Graphics card" 16 $y 200 20 $Bold)
    $y += 24
    [void](Add-Label $form "Load" 16 ($y + 6) 110)
    $load = New-Object System.Windows.Forms.TrackBar
    $load.Minimum = 40
    $load.Maximum = 100
    $load.TickFrequency = 10
    $load.SmallChange = 5
    $load.LargeChange = 10
    $load.SetBounds(126, $y, 330, 40)
    $form.Controls.Add($load)
    $loadText = Add-Label $form "" 462 ($y + 6) 100 20 $Bold
    $y += 42
    [void](Add-Label $form "Max. temperature" 16 ($y + 3) 110)
    $maxTemp = New-TempBox 126 $y
    $form.Controls.Add($maxTemp)
    [void](Add-Label $form "above it, the next frame waits until the card is 3 $Deg cooler" 216 ($y + 4) ($W - 230) 18 $Small $Slate)
    $y += 30
    [void](Add-Label $form ("Less than 100 % = a pause after every frame: at 70 % the card rests 30 % of the time, " +
        "so it stays cooler and quieter; the run takes longer.") 16 $y ($W - 32) 34 $Small $Slate)
    $y += 40

    $quiet = New-Object System.Windows.Forms.CheckBox
    $quiet.Text = "Quiet hours from"
    $quiet.SetBounds(16, ($y + 2), 128, 24)
    $form.Controls.Add($quiet)
    $qStart = New-ClockPicker 146 $y $std.quiet_start
    $form.Controls.Add($qStart)
    [void](Add-Label $form "to" 222 ($y + 4) 22)
    $qEnd = New-ClockPicker 246 $y $std.quiet_end
    $form.Controls.Add($qEnd)
    [void](Add-Label $form "load" 326 ($y + 4) 34)
    $qLoad = New-Object System.Windows.Forms.NumericUpDown
    $qLoad.Minimum = 40
    $qLoad.Maximum = 100
    $qLoad.Increment = 5
    $qLoad.SetBounds(362, $y, 56, 24)
    $form.Controls.Add($qLoad)
    [void](Add-Label $form "%   max." 420 ($y + 4) 60)
    $qTemp = New-TempBox 482 $y
    $form.Controls.Add($qTemp)
    $y += 36

    [void](Add-Label $form "Models" 16 $y 200 20 $Bold)
    $y += 22
    $list = New-Object System.Windows.Forms.CheckedListBox
    $list.CheckOnClick = $true
    $list.SetBounds(16, $y, $W - 32, 150)
    $ids = New-Object System.Collections.ArrayList
    foreach ($m in $models) {
        $note = "about " + (Format-Duration ([double]$m.gpu + [double]$m.cpu)) + " at full load"
        if (-not $m.found) { $note = "file not found: skipped" }
        $i = $list.Items.Add(([string]$m.title + "   (" + $note + ")"))
        $list.SetItemChecked($i, [bool]$m.found)
        [void]$ids.Add([string]$m.id)
    }
    $form.Controls.Add($list)
    $y += 158

    [void](Add-Label $form "Start" 16 ($y + 3) 110 20 $Bold)
    $now = New-Object System.Windows.Forms.RadioButton
    $now.Text = "Now"
    $now.Checked = $true
    $now.SetBounds(126, $y, 60, 24)
    $form.Controls.Add($now)
    $at = New-Object System.Windows.Forms.RadioButton
    $at.Text = "At"
    $at.SetBounds(196, $y, 44, 24)
    $form.Controls.Add($at)
    $atTime = New-ClockPicker 242 $y "23:00"
    $form.Controls.Add($atTime)
    $y += 32
    [void](Add-Label $form "When done" 16 ($y + 3) 110 20 $Bold)
    $done = New-Object System.Windows.Forms.ComboBox
    $done.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
    [void]$done.Items.AddRange(@("Nothing", "Sleep", "Shut down"))
    $done.SetBounds(126, $y, 120, 24)
    $form.Controls.Add($done)
    [void](Add-Label $form "after a 60-second countdown you can cancel" 254 ($y + 4) ($W - 270) 18 $Small $Slate)
    $y += 36

    $expected = Add-Label $form "" 16 $y ($W - 32) 40 $Bold $GreenDark
    $y += 48

    $back = New-Button "Back to standard" 16 $y 150
    $tip = New-Object System.Windows.Forms.ToolTip
    $tip.SetToolTip($back, "Puts the kit's own settings back: 100 % load, no temperature limit, no quiet hours, nothing when done.")
    $cancel = New-Button "Cancel" ($W - 252) $y 110
    $start = New-Button "Start" ($W - 132) $y 116 $true
    $form.Controls.AddRange(@($back, $cancel, $start))
    $form.AcceptButton = $start
    $form.CancelButton = $cancel
    $form.ClientSize = New-Object System.Drawing.Size($W, ($y + 46))

    $apply = {
        param($c)
        $v = [int]$c.load
        if ($v -lt 40) { $v = 40 }
        if ($v -gt 100) { $v = 100 }
        $load.Value = $v
        Set-TempBox $maxTemp ([int]$c.max_temp)
        $quiet.Checked = [bool]$c.quiet_on
        $qStart.Value = [datetime]::Today.AddMinutes((Get-ClockMinutes ([string]$c.quiet_start)))
        $qEnd.Value = [datetime]::Today.AddMinutes((Get-ClockMinutes ([string]$c.quiet_end)))
        $q = [int]$c.quiet_load
        if ($q -lt 40) { $q = 40 }
        if ($q -gt 100) { $q = 100 }
        $qLoad.Value = $q
        Set-TempBox $qTemp ([int]$c.quiet_max_temp)
        $wd = [string]$c.when_done
        if ($wd -eq "sleep") { $done.SelectedIndex = 1 } elseif ($wd -eq "shutdown") { $done.SelectedIndex = 2 } else { $done.SelectedIndex = 0 }
    }

    $update = {
        $loadText.Text = "$($load.Value) %"
        $qOn = $quiet.Checked
        foreach ($c in @($qStart, $qEnd, $qLoad, $qTemp)) { $c.Enabled = $qOn }
        $atTime.Enabled = $at.Checked
        $continuing = ($resumeBox -ne $null -and $resumeBox.Checked)
        $list.Enabled = -not $continuing
        $gpu = 0.0
        $cpu = 0.0
        $n = 0
        if ($continuing) {
            $gpu = [double]$resume.gpu
            $cpu = [double]$resume.cpu
            $n = 1
        } else {
            for ($i = 0; $i -lt $models.Count; $i++) {
                if ($list.GetItemChecked($i)) {
                    $gpu += [double]$models[$i].gpu
                    $cpu += [double]$models[$i].cpu
                    $n += 1
                }
            }
        }
        $begin = Get-Date
        if ($at.Checked) {
            $begin = [datetime]::Today.Add($atTime.Value.TimeOfDay)
            if ($begin -le (Get-Date)) { $begin = $begin.AddDays(1) }
        }
        if ($n -eq 0) {
            $expected.Text = "Tick at least one model."
            $start.Enabled = $false
            return
        }
        $start.Enabled = $true
        $wall = Get-WallSeconds $gpu $cpu $begin $load.Value $qOn $qStart.Value.ToString("HH\:mm") $qEnd.Value.ToString("HH\:mm") ([int]$qLoad.Value)
        $end = $begin.AddSeconds($wall)
        $text = "Expected: about " + (Format-Duration $wall) + " - done at about " + $end.ToString("ddd HH\:mm")
        if ((Get-TempBox $maxTemp) -gt 0 -or ($qOn -and (Get-TempBox $qTemp) -gt 0)) { $text += ", plus any waits for the temperature" }
        $expected.Text = $text + "."
    }

    & $apply $std
    & $update
    $handler = { & $update }
    $load.add_ValueChanged($handler)
    $maxTemp.add_SelectedIndexChanged($handler)
    $quiet.add_CheckedChanged($handler)
    $qStart.add_ValueChanged($handler)
    $qEnd.add_ValueChanged($handler)
    $qLoad.add_ValueChanged($handler)
    $qTemp.add_SelectedIndexChanged($handler)
    $now.add_CheckedChanged($handler)
    $at.add_CheckedChanged($handler)
    $atTime.add_ValueChanged($handler)
    if ($resumeBox) { $resumeBox.add_CheckedChanged($handler) }
    $list.add_ItemCheck({ $form.BeginInvoke([System.Windows.Forms.MethodInvoker]{ & $update }) | Out-Null })
    $back.add_Click({ & $apply $factory; & $update })
    $start.add_Click({ $form.DialogResult = [System.Windows.Forms.DialogResult]::OK; $form.Close() })
    $cancel.add_Click({ $form.DialogResult = [System.Windows.Forms.DialogResult]::Cancel; $form.Close() })

    $result = $form.ShowDialog()
    if ($result -ne [System.Windows.Forms.DialogResult]::OK) { return 1 }

    $chosen = New-Object System.Collections.ArrayList
    for ($i = 0; $i -lt $models.Count; $i++) { if ($list.GetItemChecked($i)) { [void]$chosen.Add($ids[$i]) } }
    $whenDone = @("nothing", "sleep", "shutdown")[[math]::Max(0, $done.SelectedIndex)]
    $standard = [ordered]@{
        load = [int]$load.Value
        max_temp = [int](Get-TempBox $maxTemp)
        quiet_on = [bool]$quiet.Checked
        quiet_start = $qStart.Value.ToString("HH\:mm")
        quiet_end = $qEnd.Value.ToString("HH\:mm")
        quiet_load = [int]$qLoad.Value
        quiet_max_temp = [int](Get-TempBox $qTemp)
        when_done = $whenDone
    }
    $run = [ordered]@{}
    foreach ($k in $standard.Keys) { $run[$k] = $standard[$k] }
    $run["models"] = @($chosen.ToArray())
    $run["start_at"] = ""
    if ($at.Checked) { $run["start_at"] = $atTime.Value.ToString("HH\:mm") }
    $run["resume"] = ($resumeBox -ne $null -and $resumeBox.Checked)
    Write-Utf8 $Choices (ConvertTo-Json -InputObject $run -Depth 4)
    try {
        Write-Utf8 ([string]$est.standard_file) (ConvertTo-Json -InputObject $standard -Depth 3)
    } catch {
        Write-Host "Could not keep the choices as the standard: $($_.Exception.Message)"
    }
    return 0
}

# ---------------------------------------------------------------------------------------------------------------
# the status window
# ---------------------------------------------------------------------------------------------------------------
function Show-StatusWindow {
    $control = Join-Path $Out "control.txt"
    $statusFile = Join-Path $Out "status.json"
    $W = 460
    $form = New-Form "Fresing site pictures - running" $W 250
    $line1 = Add-Label $form "Starting..." 16 76 ($W - 32) 22 $Bold
    $line2 = Add-Label $form "" 16 100 ($W - 32) 20
    $bar = New-Object System.Windows.Forms.ProgressBar
    $bar.SetBounds(16, 126, $W - 32, 18)
    $bar.Maximum = 1000
    $form.Controls.Add($bar)
    $line3 = Add-Label $form "" 16 150 ($W - 32) 20 $null $Slate
    $pause = New-Button "Pause" 16 200 110
    $stop = New-Button "Stop" 136 200 110
    [void](Add-Label $form "Closing this window does not stop the run." 256 206 ($W - 266) 18 $Small $Slate)
    $form.Controls.AddRange(@($pause, $stop))

    $send = {
        param([string]$Word)
        try { Write-Utf8 $control $Word } catch { }
    }
    $pause.add_Click({
        if ($pause.Text -eq "Pause") { & $send "pause"; $pause.Text = "Resume" } else { & $send "run"; $pause.Text = "Pause" }
    })
    $stop.add_Click({
        $a = [System.Windows.Forms.MessageBox]::Show(
            "Stop the run? Everything finished so far is kept. Double-click the kit again to continue the rest.",
            "Fresing site pictures", [System.Windows.Forms.MessageBoxButtons]::YesNo,
            [System.Windows.Forms.MessageBoxIcon]::Question)
        if ($a -eq [System.Windows.Forms.DialogResult]::Yes) { & $send "stop"; $stop.Enabled = $false; $pause.Enabled = $false }
    })

    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 2000
    $timer.add_Tick({
        $word = ""
        try { $word = (Get-Content -LiteralPath $control -Raw).Trim().ToLower() } catch { }
        if ($word -eq "ended") { $timer.Stop(); $form.Close(); return }
        try { $s = Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json } catch { return }
        $state = [string]$s.state
        if ($s.pid -and $state -ne "finished" -and $state -ne "stopped" -and
                -not (Get-Process -Id ([int]$s.pid) -ErrorAction SilentlyContinue)) {
            $line1.Text = "The run has stopped (its black window was closed?)"
            $line2.Text = "Double-click the kit again and tick Continue to make the rest."
            $pause.Enabled = $false
            $stop.Enabled = $false
            $timer.Stop()
            return
        }
        $head = ""
        if ($s.model) { $head = "Model $($s.model_n) of $($s.models): $($s.model)" }
        switch ($state) {
            "waiting" { $head = "Waiting to start" }
            "paused" { $head = "Paused - press Resume to go on" }
            "cooling" { $head = "Waiting for the graphics card to cool down" }
            "finished" { $head = "Done" }
            "stopped" { $head = "Stopped - what is done is kept" }
        }
        $line1.Text = $head
        $line2.Text = [string]$s.step
        if ($s.pct -ne $null) { $bar.Value = [int][math]::Min(1000, [math]::Max(0, [double]$s.pct * 10)) }
        $bits = @()
        if ($s.pct -ne $null) { $bits += ("{0:0} % done" -f [double]$s.pct) }
        if ($s.load -ne $null) { $bits += "load $($s.load) %" }
        if ($s.temp -ne $null) { $bits += ("{0:0} $Deg" -f [double]$s.temp) + "C" }
        if ($s.end) { $bits += "done at about $($s.end)" }
        $line3.Text = $bits -join "   |   "
        if ($state -eq "paused") { $pause.Text = "Resume" } elseif ($state -ne "stopped") { $pause.Text = "Pause" }
        if ($state -eq "finished" -or $state -eq "stopped") { $pause.Enabled = $false; $stop.Enabled = $false }
    })
    $timer.Start()
    [void]$form.ShowDialog()
    return 0
}

# ---------------------------------------------------------------------------------------------------------------
# when done: sleep or shut down after a countdown
# ---------------------------------------------------------------------------------------------------------------
function Show-EndCountdown {
    if ($Code -eq 4) { return 0 }                       # stopped by hand: the owner is there
    try { $c = Get-Content -LiteralPath $Choices -Raw | ConvertFrom-Json } catch { return 0 }
    $what = [string]$c.when_done
    if ($what -ne "sleep" -and $what -ne "shutdown") { return 0 }
    $verb = "go to sleep"
    if ($what -eq "shutdown") { $verb = "shut down" }
    $W = 420
    $form = New-Form "Fresing site pictures - done" $W 190
    $form.TopMost = $true
    $left = 60
    $msg = Add-Label $form "" 16 80 ($W - 32) 44 $Bold
    $go = New-Button "Now" ($W - 252) 140 110 $true
    $cancel = New-Button "Cancel" ($W - 132) 140 116
    $form.Controls.AddRange(@($go, $cancel))
    $form.CancelButton = $cancel
    $show = { $msg.Text = "The pictures are done. The PC will $verb in $left s." }
    & $show
    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 1000
    $timer.add_Tick({
        $script:left -= 1
        $left = $script:left
        & $show
        if ($script:left -le 0) { $timer.Stop(); $form.DialogResult = [System.Windows.Forms.DialogResult]::OK; $form.Close() }
    })
    $script:left = 60
    $go.add_Click({ $timer.Stop(); $form.DialogResult = [System.Windows.Forms.DialogResult]::OK; $form.Close() })
    $cancel.add_Click({ $timer.Stop(); $form.DialogResult = [System.Windows.Forms.DialogResult]::Cancel; $form.Close() })
    $timer.Start()
    $r = $form.ShowDialog()
    if ($r -ne [System.Windows.Forms.DialogResult]::OK) { Write-Host "Cancelled: the PC stays on."; return 0 }
    if ($what -eq "shutdown") {
        & shutdown.exe /s /t 0
    } else {
        [void][System.Windows.Forms.Application]::SetSuspendState([System.Windows.Forms.PowerState]::Suspend, $false, $false)
    }
    return 0
}

$exitCode = 0
try {
    switch ($Mode) {
        "start" { $r = @(Show-StartWindow) }
        "status" { $r = @(Show-StatusWindow) }
        "end" { $r = @(Show-EndCountdown) }
        default { Write-Host "unknown -Mode $Mode"; $r = @(2) }
    }
    $exitCode = [int]$r[-1]                             # a function's stray output must not become the exit code
} catch {
    Write-Host ("The window could not open: " + $_.Exception.Message)
    $exitCode = 2
}
exit $exitCode
