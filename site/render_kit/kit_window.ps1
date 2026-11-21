<#
  Fresing site kit - the start window, the status window and the end countdown (task 0144).

  Started by "Make site pictures.bat" with Windows PowerShell 5.1 (part of Windows; nothing to install):
    -Mode start  -Estimate <estimate.json> -Choices <run_choices.json>
        The start window: graphics-card load, max temperature, quiet hours, models, start time, when done, continue a
        stopped run. Writes the choices for make_site_pictures.py (--choices=) and keeps them as the standard in
        %LOCALAPPDATA%\Fresing Render\site_kit.json (outside the kit, so a new kit keeps them).
        Exit 0 = Start, 10 = Cancel. Anything else (1 = PowerShell could not run the script): the .bat asks in the
        console instead.
    -Mode status -Out <output folder>
        The small status window: reads output\status.json every 2 s, writes pause / run / stop to output\control.txt.
        Closes itself when the .bat writes "ended" there.
    -Mode end    -Choices <run_choices.json> -Code <exit code of the run>
        When done = sleep or shut down: a 60-second countdown with Cancel, then does it (no admin rights needed).
    -Mode lib    only defines the functions (the tests).
    -Mode layout loads Windows Forms and defines the window builders without showing anything: the layout check
                 (tools/ci_kit_window_layout.ps1) builds the windows with -TestScale / -TestScreen.

  Layout (task 0177): nothing is placed at fixed 96-DPI pixels. Every distance goes through Px (the screen's DPI / 96),
  every text is measured with its own font (TextRenderer, as the controls draw it), long hints wrap and the window grows
  to fit them; a start window taller than the screen's working area scrolls its middle part, the buttons stay visible.
  -TestScale multiplies the fonts and distances as a display scale would on a 96-DPI screen (the check on GitHub).

  This file must stay plain ASCII (Windows PowerShell 5.1 reads a file without a BOM as ANSI) with CRLF line ends.
  Get-WallSeconds is the same loop as kit_run.wall_seconds (a test compares them).
#>
param(
    [string]$Mode = "start",
    [string]$Estimate = "",
    [string]$Choices = "",
    [string]$Out = "",
    [int]$Code = 0,
    [double]$TestScale = 1.0,
    [string]$TestScreen = ""
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

try {                                                   # a failure here: exit 2, the .bat asks in the console
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
try {
    Add-Type -Namespace FresingKit -Name Dpi -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
    [void][FresingKit.Dpi]::SetProcessDPIAware()
} catch { }
[System.Windows.Forms.Application]::EnableVisualStyles()
# labels draw with GDI (TextRenderer), as they are measured; only possible before the first window
try { [System.Windows.Forms.Application]::SetCompatibleTextRenderingDefault($false) } catch { }

if ($TestScale -le 0) { $TestScale = 1.0 }
$g = [System.Drawing.Graphics]::FromHwnd([IntPtr]::Zero)
$UiScale = $g.DpiX / 96.0 * $TestScale                 # 1.5 at 150 % display scale
$g.Dispose()

function New-Color([string]$Hex) { return [System.Drawing.ColorTranslator]::FromHtml($Hex) }
function New-UiFont([double]$Points, $Style = [System.Drawing.FontStyle]::Regular) {
    return New-Object System.Drawing.Font("Segoe UI", ($Points * $TestScale), $Style)   # points: Windows scales them
}
$Green = New-Color "#479B29"
$GreenDark = New-Color "#2F6A1B"
$Charcoal = New-Color "#252E36"
$Slate = New-Color "#5B6670"
$Mist = New-Color "#F1F3F5"
$Deep = New-Color "#1A2027"
$Font = New-UiFont 9.75
$Bold = New-UiFont 9.75 ([System.Drawing.FontStyle]::Bold)
$Small = New-UiFont 8.5
$TitleFont = New-UiFont 12
$TextFlags = [System.Windows.Forms.TextFormatFlags]::WordBreak -bor [System.Windows.Forms.TextFormatFlags]::TextBoxControl -bor
             [System.Windows.Forms.TextFormatFlags]::NoPrefix
} catch {
    Write-Host ("The window could not open: " + $_.Exception.Message)
    exit 2
}

# ---------------------------------------------------------------------------------------------------------------
# layout helpers: sizes from the DPI and the measured texts
# ---------------------------------------------------------------------------------------------------------------
function Px([double]$V) { return [int][math]::Round($V * $UiScale) }    # 96-DPI pixels -> this screen's pixels

function Get-ArrowWidth {                               # the spin / drop-down buttons of a field
    return [math]::Max([int]([System.Windows.Forms.SystemInformation]::VerticalScrollBarWidth * $TestScale), (Px 17))
}

function Measure-UiText([string]$Text, $F, [int]$MaxW = 100000) {
    $t = $Text
    if (-not $t) { $t = " " }
    return [System.Windows.Forms.TextRenderer]::MeasureText($t, $F, (New-Object System.Drawing.Size([math]::Max(1, $MaxW), 100000)), $TextFlags)
}

function Get-FitTexts($c) {                             # every text a control must fit (a button's other caption)
    if ($c.Tag -is [array]) { return @($c.Tag) }
    return @([string]$c.Text)
}

function Get-Natural($c) {                              # the size a control needs for its text at this scale
    $f = $c.Font
    $arrow = Get-ArrowWidth
    if ($c -is [System.Windows.Forms.Label]) {
        $m = Measure-UiText $c.Text $f
        return New-Object System.Drawing.Size(($m.Width + (Px 3)), ($m.Height + (Px 2)))
    }
    if ($c -is [System.Windows.Forms.CheckBox] -or $c -is [System.Windows.Forms.RadioButton]) {
        $m = Measure-UiText $c.Text $f
        $p = $c.GetPreferredSize([System.Drawing.Size]::Empty)
        $w = [math]::Max($p.Width, $m.Width + (Px 22)) + (Px 4)
        $h = [math]::Max([math]::Max($p.Height, $m.Height), (Px 16)) + (Px 4)
        return New-Object System.Drawing.Size($w, $h)
    }
    if ($c -is [System.Windows.Forms.Button]) {
        $w = Px 110
        foreach ($t in (Get-FitTexts $c)) { $w = [math]::Max($w, (Measure-UiText $t $f).Width + (Px 28)) }
        return New-Object System.Drawing.Size($w, [math]::Max((Px 30), $f.Height + (Px 14)))
    }
    if ($c -is [System.Windows.Forms.ComboBox]) {
        $w = 0
        foreach ($t in $c.Items) { $w = [math]::Max($w, (Measure-UiText ([string]$t) $f).Width) }
        return New-Object System.Drawing.Size(($w + $arrow + (Px 14)), $c.PreferredHeight)
    }
    if ($c -is [System.Windows.Forms.DateTimePicker]) {
        $w = (Measure-UiText "88:88" $f).Width
        return New-Object System.Drawing.Size(($w + $arrow + (Px 16)), $c.PreferredHeight)
    }
    if ($c -is [System.Windows.Forms.NumericUpDown]) {
        $w = (Measure-UiText "100" $f).Width
        return New-Object System.Drawing.Size(($w + $arrow + (Px 16)), $c.PreferredHeight)
    }
    return New-Object System.Drawing.Size((Px 100), $c.Height)
}

function Set-Row([array]$Items, [int]$X0, [int]$Y, [int]$Right, [int]$Indent = -1) {
    <# Places controls left to right from X0, vertically centred on their line; returns the bottom of the last line.
       An item: @{ c = control; w = width (else its natural width); gap = space before it (else Px 6);
       brk = a new line may start here (else it stays with the item before it); fill = a label that takes the rest of
       the line and wraps (minw: else it goes onto a line of its own) }. A new line starts at Indent. #>
    if ($Indent -lt 0) { $Indent = $X0 }
    $segs = [System.Collections.ArrayList]::new()
    foreach ($it in $Items) {
        if ($segs.Count -eq 0 -or $it.brk -or $it.fill) { [void]$segs.Add([System.Collections.ArrayList]::new()) }
        [void]$segs[$segs.Count - 1].Add($it)
    }
    $lines = [System.Collections.ArrayList]::new()
    $line = [System.Collections.ArrayList]::new()
    $x = $X0
    foreach ($seg in $segs) {
        $first = $seg[0]
        if ($first.fill) {
            $gap = 0
            if ($line.Count) { $gap = Px 6; if ($first.ContainsKey("gap")) { $gap = $first.gap } }
            $minw = Px 150
            if ($first.minw) { $minw = $first.minw }
            if ($line.Count -and ($Right - $x - $gap) -lt $minw) {
                [void]$lines.Add($line); $line = [System.Collections.ArrayList]::new(); $x = $Indent; $gap = 0
            }
            $w = $Right - $x - $gap
            $m = Measure-UiText $first.c.Text $first.c.Font ($w - (Px 3))
            [void]$line.Add(@{ c = $first.c; x = ($x + $gap); w = $w; h = ($m.Height + (Px 2)) })
            $x = $Right
            continue
        }
        $sizes = @()
        $segW = 0
        for ($i = 0; $i -lt $seg.Count; $i++) {
            $it = $seg[$i]
            $n = Get-Natural $it.c
            $w = $n.Width
            if ($it.w) { $w = $it.w }
            $gap = Px 6
            if ($it.ContainsKey("gap")) { $gap = $it.gap }
            $sizes += , @($w, $n.Height, $gap)
            $segW += $w
            if ($i -gt 0) { $segW += $gap }
        }
        $lead = 0
        if ($line.Count) { $lead = $sizes[0][2] }
        if ($line.Count -and ($x + $lead + $segW) -gt $Right) {
            [void]$lines.Add($line); $line = [System.Collections.ArrayList]::new(); $x = $Indent; $lead = 0
        }
        for ($i = 0; $i -lt $seg.Count; $i++) {
            if ($i -eq 0) { $x += $lead } else { $x += $sizes[$i][2] }
            [void]$line.Add(@{ c = $seg[$i].c; x = $x; w = $sizes[$i][0]; h = $sizes[$i][1] })
            $x += $sizes[$i][0]
        }
    }
    if ($line.Count) { [void]$lines.Add($line) }
    $bottom = $Y
    foreach ($ln in $lines) {
        $rowH = 0
        foreach ($p in $ln) { $rowH = [math]::Max($rowH, $p.h) }
        foreach ($p in $ln) { $p.c.SetBounds($p.x, ($Y + [int][math]::Floor(($rowH - $p.h) / 2)), $p.w, $p.h) }
        $bottom = $Y + $rowH
        $Y = $bottom + (Px 4)
    }
    return $bottom
}

function Get-WorkArea {                                 # where the window must fit (pixels)
    if ($TestScreen -match '^(\d+)x(\d+)$') {
        return New-Object System.Drawing.Rectangle(0, 0, [int]$Matches[1], ([int]$Matches[2] - [int](48 * $TestScale)))
    }
    return [System.Windows.Forms.Screen]::FromPoint([System.Windows.Forms.Cursor]::Position).WorkingArea
}

function Get-FrameHeight($Form) {                       # title bar + borders (a 96-DPI frame in the check: scaled)
    return [int](($Form.Height - $Form.ClientSize.Height) * $TestScale)
}

function Set-ClientSize($Form, [int]$W, [int]$H) {
    if ($Form.WindowState -ne [System.Windows.Forms.FormWindowState]::Normal) { return }   # minimised: leave it alone
    $Form.Tag = New-Object System.Drawing.Size($W, $H)      # what it should be (the check compares)
    if ($Form.ClientSize.Width -ne $W -or $Form.ClientSize.Height -ne $H) {
        $Form.ClientSize = New-Object System.Drawing.Size($W, $H)
    }
}

# ---------------------------------------------------------------------------------------------------------------
# controls
# ---------------------------------------------------------------------------------------------------------------
function New-Text([string]$Text, $F = $null, $Color = $null) {
    $l = New-Object System.Windows.Forms.Label
    $l.AutoSize = $false
    $l.UseMnemonic = $false
    $l.Text = $Text
    if ($F) { $l.Font = $F } else { $l.Font = $Font }
    if ($Color) { $l.ForeColor = $Color }
    return $l
}

function New-Button([string]$Text, [bool]$Primary = $false, [string[]]$Fit = $null) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $Text
    $b.Font = $Font
    $b.UseMnemonic = $false
    if ($Fit) { $b.Tag = $Fit }
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

function New-Choice([string]$Kind, [string]$Text, $F = $null) {       # a CheckBox or RadioButton
    $c = New-Object ("System.Windows.Forms." + $Kind)
    $c.Text = $Text
    $c.UseMnemonic = $false
    if ($F) { $c.Font = $F } else { $c.Font = $Font }
    return $c
}

function New-TempBox {
    $c = New-Object System.Windows.Forms.ComboBox
    $c.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
    $c.Font = $Font
    [void]$c.Items.Add("Off")
    for ($t = 70; $t -le 85; $t++) { [void]$c.Items.Add("$t $Deg" + "C") }
    return $c
}

function Set-TempBox($Box, [int]$Value) {
    if ($Value -ge 70 -and $Value -le 85) { $Box.SelectedIndex = $Value - 69 } else { $Box.SelectedIndex = 0 }
}

function Get-TempBox($Box) {
    if ($Box.SelectedIndex -le 0) { return 0 }
    return 69 + $Box.SelectedIndex
}

function New-ClockPicker([string]$Clock) {
    $d = New-Object System.Windows.Forms.DateTimePicker
    $d.Format = [System.Windows.Forms.DateTimePickerFormat]::Custom
    $d.CustomFormat = "HH:mm"
    $d.ShowUpDown = $true
    $d.Font = $Font
    $d.Value = [datetime]::Today.AddMinutes((Get-ClockMinutes $Clock))
    return $d
}

function New-Form([string]$Title) {
    $f = New-Object System.Windows.Forms.Form
    $f.Text = $Title
    $f.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::None    # everything below is in this screen's pixels
    $f.Font = $Font
    $f.BackColor = $Mist
    $f.ForeColor = $Charcoal
    $f.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
    $f.MaximizeBox = $false
    $f.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
    $f.add_Shown({ $was = $this.TopMost; $this.TopMost = $true; $this.Activate(); $this.TopMost = $was })   # to the front
    $head = New-Object System.Windows.Forms.Panel
    $head.BackColor = $Deep
    $pic = $null
    $logo = Join-Path $PSScriptRoot "fresing_logo.png"
    if (Test-Path -LiteralPath $logo) {
        $pic = New-Object System.Windows.Forms.PictureBox
        $pic.SizeMode = [System.Windows.Forms.PictureBoxSizeMode]::Zoom
        $pic.Image = [System.Drawing.Image]::FromFile($logo)
        $head.Controls.Add($pic)
    }
    $t = New-Text "Site pictures" $TitleFont ([System.Drawing.Color]::White)
    $head.Controls.Add($t)
    $f.Controls.Add($head)
    return @{ form = $f; head = $head; pic = $pic; title = $t }
}

function Set-Head($U) {                                 # the dark band with the logo; returns its height
    $hh = Px 64
    $U.head.SetBounds(0, 0, $U.W, $hh)
    if ($U.pic) { $U.pic.SetBounds((Px 16), (Px 10), (Px 152), (Px 44)) }
    $n = Get-Natural $U.title
    $U.title.SetBounds(($U.W - (Px 16) - $n.Width), [int](($hh - $n.Height) / 2), $n.Width, $n.Height)
    return $hh
}

# ---------------------------------------------------------------------------------------------------------------
# the start window
# ---------------------------------------------------------------------------------------------------------------
$ExpectedLongest = "Expected: about 188 h 58 min - done at about Wed 23:58, plus any waits for the temperature."

function Build-StartWindow($Est) {
    $std = $Est.standard
    $resume = $Est.resume
    $models = @($Est.models)
    $u = New-Form "Fresing site pictures - start"
    $u.W = Px 580
    $form = $u.form
    $body = New-Object System.Windows.Forms.Panel        # the settings + models: scrolls on a small screen
    $foot = New-Object System.Windows.Forms.Panel        # the expected time and the buttons: always visible
    $u.body = $body
    $u.foot = $foot

    $u.resumeBox = $null
    if ($resume) {
        $u.resumeBox = New-Choice "CheckBox" ([string]$resume.text) $Bold
        $u.resumeBox.Checked = $true
        $u.resumeHint = New-Text "Makes only the pictures and clips that are not done yet. Untick it to start a new run." $Small $Slate
        $body.Controls.AddRange(@($u.resumeBox, $u.resumeHint))
    }
    $u.hGpu = New-Text "Graphics card" $Bold
    $u.lLoad = New-Text "Load"
    $load = New-Object System.Windows.Forms.TrackBar
    $load.Minimum = 40
    $load.Maximum = 100
    $load.TickFrequency = 10
    $load.SmallChange = 5
    $load.LargeChange = 10
    $u.load = $load
    $u.loadText = New-Text "100 %" $Bold
    $u.lTemp = New-Text "Max. temperature"
    $u.maxTemp = New-TempBox
    $u.tempHint = New-Text "above it, the next frame waits until the card is 3 $Deg cooler" $Small $Slate
    $u.loadHint = New-Text ("Less than 100 % = a pause after every frame: at 70 % the card rests 30 % of the time, " +
        "so it stays cooler and quieter; the run takes longer.") $Small $Slate
    $u.quiet = New-Choice "CheckBox" "Quiet hours from"
    $u.qStart = New-ClockPicker $std.quiet_start
    $u.lTo = New-Text "to"
    $u.qEnd = New-ClockPicker $std.quiet_end
    $u.lQLoad = New-Text "load"
    $qLoad = New-Object System.Windows.Forms.NumericUpDown
    $qLoad.Minimum = 40
    $qLoad.Maximum = 100
    $qLoad.Increment = 5
    $qLoad.Font = $Font
    $u.qLoad = $qLoad
    $u.lPct = New-Text "%"
    $u.lMax = New-Text "max."
    $u.qTemp = New-TempBox
    $body.Controls.AddRange(@($u.hGpu, $u.lLoad, $load, $u.loadText, $u.lTemp, $u.maxTemp, $u.tempHint, $u.loadHint,
        $u.quiet, $u.qStart, $u.lTo, $u.qEnd, $u.lQLoad, $qLoad, $u.lPct, $u.lMax, $u.qTemp))

    $u.hModels = New-Text "Models" $Bold
    $list = New-Object System.Windows.Forms.ListView     # check box + name | time: the time has its own column
    $list.View = [System.Windows.Forms.View]::Details
    $list.CheckBoxes = $true
    $list.FullRowSelect = $true
    $list.MultiSelect = $false
    $list.HideSelection = $true
    $list.HeaderStyle = [System.Windows.Forms.ColumnHeaderStyle]::Nonclickable
    $list.Font = $Font
    [void]$list.Columns.Add("Model")
    [void]$list.Columns.Add("Time at full load")
    $u.ids = [System.Collections.ArrayList]::new()
    foreach ($m in $models) {
        $note = "about " + (Format-Duration ([double]$m.gpu + [double]$m.cpu))
        if (-not $m.found) { $note = "file not found: skipped" }
        $item = New-Object System.Windows.Forms.ListViewItem([string]$m.title)
        [void]$item.SubItems.Add($note)
        $tick = $true                                     # task 0268: a run choice ticked by models.ini, the rest not
        if ($m.PSObject.Properties.Name -contains "ticked") { $tick = [bool]$m.ticked }
        $item.Checked = ([bool]$m.found -and $tick)
        [void]$list.Items.Add($item)
        [void]$u.ids.Add([string]$m.id)
    }
    $u.list = $list
    $body.Controls.AddRange(@($u.hModels, $list))

    $u.lStart = New-Text "Start" $Bold
    $u.now = New-Choice "RadioButton" "Now"
    $u.now.Checked = $true
    $u.at = New-Choice "RadioButton" "At"
    $u.atTime = New-ClockPicker "23:00"
    $u.lDone = New-Text "When done" $Bold
    $done = New-Object System.Windows.Forms.ComboBox
    $done.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
    $done.Font = $Font
    [void]$done.Items.AddRange(@("Nothing", "Sleep", "Shut down"))
    $u.done = $done
    $u.doneHint = New-Text "after a 60-second countdown you can cancel" $Small $Slate
    $body.Controls.AddRange(@($u.lStart, $u.now, $u.at, $u.atTime, $u.lDone, $done, $u.doneHint))

    $u.expected = New-Text "" $Bold $GreenDark
    $u.back = New-Button "Back to standard"
    $u.cancel = New-Button "Cancel"
    $u.start = New-Button "Start" $true
    $foot.Controls.AddRange(@($u.expected, $u.back, $u.cancel, $u.start))
    $form.Controls.AddRange(@($body, $foot))
    $form.AcceptButton = $u.start
    $form.CancelButton = $u.cancel
    Set-StartLayout $u
    return $u
}

function Set-ListSize($U, [int]$X, [int]$Y, [int]$Width) {   # all models visible, the time column fits its texts
    $lv = $U.list
    $lv.SetBounds($X, $Y, $Width, (Px 600))         # tall: no scroll bar while the columns are set
    $null = $lv.Handle                                  # item rectangles need the window
    $c2 = (Measure-UiText $lv.Columns[1].Text $lv.Font).Width
    foreach ($it in $lv.Items) { $c2 = [math]::Max($c2, (Measure-UiText $it.SubItems[1].Text $lv.Font).Width) }
    $c2 += Px 24
    $lv.Columns[1].Width = $c2
    $lv.Columns[0].Width = [math]::Max((Px 60), $lv.ClientSize.Width - $c2 - 1)
    $frame = $lv.Height - $lv.ClientSize.Height
    $n = [math]::Max(1, $lv.Items.Count)
    $top = $lv.Font.Height + (Px 10)
    $ih = $lv.Font.Height + (Px 4)
    if ($lv.Items.Count -gt 0) {
        $r = $lv.GetItemRect(0)
        if ($r.Height -gt 0) { $top = $r.Top; $ih = $r.Height }
    }
    $lv.Height = $top + $n * $ih + $frame + (Px 3)
    return $lv.Bottom
}

function Set-StartBody($U, [int]$Right) {               # the settings and models inside the body; returns its height
    $M = Px 16
    $col = 0
    foreach ($l in @($U.lLoad, $U.lTemp, $U.lStart, $U.lDone)) { $col = [math]::Max($col, (Get-Natural $l).Width) }
    $col += Px 10
    $y = Px 12
    if ($U.resumeBox) {
        $y = Set-Row @(@{ c = $U.resumeBox; fill = $false }) $M $y $Right
        $y = Set-Row @(@{ c = $U.resumeHint; fill = $true }) ($M + (Px 20)) ($y + (Px 1)) $Right
        $y += Px 14
    }
    $y = Set-Row @(@{ c = $U.hGpu }) $M $y $Right
    $y += Px 6
    $ltw = (Get-Natural $U.loadText).Width + (Px 4)
    $trackW = $Right - ($M + $col) - (Px 6) - $ltw
    $y = Set-Row @(@{ c = $U.lLoad; w = $col }, @{ c = $U.load; w = $trackW; gap = 0 }, @{ c = $U.loadText; w = $ltw }) $M $y $Right
    $y += Px 6
    $y = Set-Row @(@{ c = $U.lTemp; w = $col }, @{ c = $U.maxTemp; gap = 0 },
        @{ c = $U.tempHint; fill = $true; minw = (Px 170); gap = (Px 10) }) $M $y $Right ($M + $col)
    $y += Px 6
    $y = Set-Row @(@{ c = $U.loadHint; fill = $true }) $M $y $Right
    $y += Px 14
    $y = Set-Row @(@{ c = $U.quiet }, @{ c = $U.qStart; gap = (Px 2) }, @{ c = $U.lTo }, @{ c = $U.qEnd },
        @{ c = $U.lQLoad; brk = $true; gap = (Px 16) }, @{ c = $U.qLoad }, @{ c = $U.lPct; gap = (Px 3) },
        @{ c = $U.lMax; gap = (Px 12) }, @{ c = $U.qTemp }) $M $y $Right ($M + (Px 20))
    $y += Px 16
    $y = Set-Row @(@{ c = $U.hModels }) $M $y $Right
    $y += Px 4
    $y = Set-ListSize $U $M $y ($Right - $M)
    $y += Px 14
    $y = Set-Row @(@{ c = $U.lStart; w = $col }, @{ c = $U.now; gap = 0 }, @{ c = $U.at; gap = (Px 10) },
        @{ c = $U.atTime; gap = 0 }) $M $y $Right ($M + $col)
    $y += Px 8
    $y = Set-Row @(@{ c = $U.lDone; w = $col }, @{ c = $U.done; gap = 0 },
        @{ c = $U.doneHint; fill = $true; minw = (Px 170); gap = (Px 10) }) $M $y $Right ($M + $col)
    return $y + (Px 12)
}

function Set-StartLayout($U) {
    $W = $U.W
    $M = Px 16
    $headH = Set-Head $U
    # the foot: the expected time (room for its longest text) and the buttons
    $expH = (Measure-UiText $ExpectedLongest $U.expected.Font ($W - 2 * $M - (Px 3))).Height + (Px 2)
    $fy = Px 8
    $U.expected.SetBounds($M, $fy, ($W - 2 * $M), $expH)
    $fy += $expH + (Px 10)
    $nb = Get-Natural $U.back
    $nc = Get-Natural $U.cancel
    $ns = Get-Natural $U.start
    $bh = [math]::Max($nb.Height, [math]::Max($nc.Height, $ns.Height))
    $U.start.SetBounds(($W - $M - $ns.Width), $fy, $ns.Width, $bh)
    $U.cancel.SetBounds(($W - $M - $ns.Width - (Px 10) - $nc.Width), $fy, $nc.Width, $bh)
    $U.back.SetBounds($M, $fy, $nb.Width, $bh)
    $footH = $fy + $bh + (Px 14)
    # the body: all of it, or as much as the screen allows and a scroll bar
    $form = $U.form
    Set-ClientSize $form $W (Px 400)
    $maxClient = (Get-WorkArea).Height - (Get-FrameHeight $form)
    $U.body.AutoScroll = $false
    $bodyH = Set-StartBody $U ($W - $M)
    if ($headH + $bodyH + $footH -gt $maxClient) {
        $U.body.AutoScroll = $true
        [void](Set-StartBody $U ($W - $M - (Get-ArrowWidth)))
        $bodyH = [math]::Max((Px 120), $maxClient - $headH - $footH)
    }
    $U.body.SetBounds(0, $headH, $W, $bodyH)
    $U.foot.SetBounds(0, ($headH + $bodyH), $W, $footH)
    $U.scrolls = $U.body.AutoScroll
    Set-ClientSize $form $W ($headH + $bodyH + $footH)
}

function Show-StartWindow {
    $est = Get-Content -LiteralPath $Estimate -Raw | ConvertFrom-Json
    $std = $est.standard
    $factory = $est.factory
    $resume = $est.resume
    $models = @($est.models)

    $u = Build-StartWindow $est
    $form = $u.form
    $resumeBox = $u.resumeBox
    $load = $u.load
    $loadText = $u.loadText
    $maxTemp = $u.maxTemp
    $quiet = $u.quiet
    $qStart = $u.qStart
    $qEnd = $u.qEnd
    $qLoad = $u.qLoad
    $qTemp = $u.qTemp
    $list = $u.list
    $ids = $u.ids
    $now = $u.now
    $at = $u.at
    $atTime = $u.atTime
    $done = $u.done
    $expected = $u.expected
    $back = $u.back
    $cancel = $u.cancel
    $start = $u.start
    $tip = New-Object System.Windows.Forms.ToolTip
    $tip.SetToolTip($back, "Puts the kit's own settings back: 100 % load, no temperature limit, no quiet hours, nothing when done.")

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
                if ($list.Items[$i].Checked) {
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
        $text = "Expected: about " + (Format-Duration $wall) + " - done at about " + $end.ToString("ddd HH\:mm", [System.Globalization.CultureInfo]::InvariantCulture)
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
    $list.add_ItemChecked($handler)
    if ($u.scrolls) {                                   # the wheel over the slider or the number box scrolls the window,
        $wheel = {                                      # it must not change the load unnoticed
            param($sender, $e)
            $e.Handled = $true
            $u.body.AutoScrollPosition = New-Object System.Drawing.Point(0, ([math]::Max(0, -$u.body.AutoScrollPosition.Y - $e.Delta)))
        }
        $load.add_MouseWheel($wheel)
        $qLoad.add_MouseWheel($wheel)
    }
    $back.add_Click({ & $apply $factory; & $update })
    $start.add_Click({ $form.DialogResult = [System.Windows.Forms.DialogResult]::OK; $form.Close() })
    $cancel.add_Click({ $form.DialogResult = [System.Windows.Forms.DialogResult]::Cancel; $form.Close() })

    if ($TestOnShown) { $form.add_Shown($TestOnShown) }   # the layout check clicks through the window
    $result = $form.ShowDialog()
    if ($result -ne [System.Windows.Forms.DialogResult]::OK) { return 10 }

    $chosen = New-Object System.Collections.ArrayList
    for ($i = 0; $i -lt $models.Count; $i++) { if ($list.Items[$i].Checked) { [void]$chosen.Add($ids[$i]) } }
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
function Build-StatusWindow {
    $u = New-Form "Fresing site pictures - running"
    $u.W = Px 460
    $u.line1 = New-Text "Starting..." $Bold
    $u.line2 = New-Text ""
    $u.bar = New-Object System.Windows.Forms.ProgressBar
    $u.bar.Maximum = 1000
    $u.line3 = New-Text "" $Font $Slate
    $u.pause = New-Button "Pause" $false @("Pause", "Resume")
    $u.stop = New-Button "Stop"
    $u.hint = New-Text "Closing this window does not stop the run." $Small $Slate
    $u.form.Controls.AddRange(@($u.line1, $u.line2, $u.bar, $u.line3, $u.pause, $u.stop, $u.hint))
    Set-StatusLayout $u
    return $u
}

function Set-StatusLayout($U) {                         # again after every new text: long lines wrap, the window grows
    $W = $U.W
    $M = Px 16
    $R = $W - $M
    $y = (Set-Head $U) + (Px 12)
    $y = Set-Row @(@{ c = $U.line1; fill = $true }) $M $y $R
    $y = Set-Row @(@{ c = $U.line2; fill = $true }) $M ($y + (Px 4)) $R
    $y += Px 8
    $U.bar.SetBounds($M, $y, ($R - $M), (Px 18))
    $y += Px 26
    $y = Set-Row @(@{ c = $U.line3; fill = $true }) $M $y $R
    $y += Px 18
    $y = Set-Row @(@{ c = $U.pause }, @{ c = $U.stop; gap = (Px 10) }, @{ c = $U.hint; fill = $true; minw = (Px 140); gap = (Px 10) }) $M $y $R
    $h = $y + (Px 14)
    if ($U.tallest -gt $h) { $h = $U.tallest }          # never shrinks: Pause and Stop do not jump under the mouse
    $U.tallest = $h
    Set-ClientSize $U.form $W $h
}

function Show-StatusWindow {
    $control = Join-Path $Out "control.txt"
    $statusFile = Join-Path $Out "status.json"
    $u = Build-StatusWindow
    $form = $u.form
    $line1 = $u.line1
    $line2 = $u.line2
    $line3 = $u.line3
    $bar = $u.bar
    $pause = $u.pause
    $stop = $u.stop

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

    $form.add_FormClosing({
        param($sender, $e)
        $asked = ""
        try { $asked = (Get-Content -LiteralPath $control -Raw).Trim().ToLower() } catch { }
        if ($pause.Enabled -and ($pause.Text -eq "Resume" -or $asked -eq "pause")) {
            $a = [System.Windows.Forms.MessageBox]::Show(
                "The run is paused and nothing could resume it once this window is closed. Resume the run and close?",
                "Fresing site pictures", [System.Windows.Forms.MessageBoxButtons]::YesNo,
                [System.Windows.Forms.MessageBoxIcon]::Question)
            if ($a -eq [System.Windows.Forms.DialogResult]::Yes) { & $send "run" } else { $e.Cancel = $true }
        }
    })
    $script:gone = $false
    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 2000
    $timer.add_Tick({
        $word = ""
        try { $word = (Get-Content -LiteralPath $control -Raw).Trim().ToLower() } catch { }
        if ($word -eq "ended") { $timer.Stop(); $pause.Enabled = $false; $form.Close(); return }
        if ($script:gone) { return }
        try { $s = Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json } catch { return }
        $state = [string]$s.state
        if ($s.pid -and $state -ne "finished" -and $state -ne "stopped" -and
                -not (Get-Process -Id ([int]$s.pid) -ErrorAction SilentlyContinue)) {
            $line1.Text = "The run has stopped (its black window was closed?)"
            $line2.Text = "Double-click the kit again and tick Continue to make the rest."
            $pause.Enabled = $false
            $stop.Enabled = $false
            Set-StatusLayout $u
            $script:gone = $true                            # keep looking for "ended": the .bat closes the window
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
        if ($word -eq "pause" -and $state -ne "paused" -and $state -ne "finished" -and $state -ne "stopped") {
            $head = "Pausing - after the picture being made"     # the run reads Pause only between frames
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
        # control.txt says what was asked: the run is slow to show "paused" (a long still), the button must not flip back
        if ($state -eq "paused" -or $word -eq "pause") { $pause.Text = "Resume" } elseif ($state -ne "stopped") { $pause.Text = "Pause" }
        if ($state -eq "finished" -or $state -eq "stopped") { $pause.Enabled = $false; $stop.Enabled = $false }
        Set-StatusLayout $u
    })
    $timer.Start()
    [void]$form.ShowDialog()
    return 0
}

# ---------------------------------------------------------------------------------------------------------------
# when done: sleep or shut down after a countdown
# ---------------------------------------------------------------------------------------------------------------
function Build-EndWindow([string]$Verb) {
    $u = New-Form "Fresing site pictures - done"
    $u.W = Px 420
    $u.msg = New-Text "" $Bold
    $u.go = New-Button "Now" $true
    $u.cancel = New-Button "Cancel"
    $u.form.Controls.AddRange(@($u.msg, $u.go, $u.cancel))
    $W = $u.W
    $M = Px 16
    $y = (Set-Head $u) + (Px 12)
    $h = (Measure-UiText "The pictures are done. The PC will $Verb in 60 s." $Bold ($W - 2 * $M - (Px 3))).Height + (Px 2)
    $u.msg.SetBounds($M, $y, ($W - 2 * $M), $h)
    $y += $h + (Px 12)
    $ng = Get-Natural $u.go
    $nc = Get-Natural $u.cancel
    $u.cancel.SetBounds(($W - $M - $nc.Width), $y, $nc.Width, $nc.Height)
    $u.go.SetBounds(($W - $M - $nc.Width - (Px 10) - $ng.Width), $y, $ng.Width, $ng.Height)
    Set-ClientSize $u.form $W ($y + $nc.Height + (Px 14))
    return $u
}

function Show-EndCountdown {
    if ($Code -ne 0 -and $Code -ne 1) { return 0 }      # only after a finished run (1 = with problems); not after
                                                        # Stop (4: the owner is there) or a crash
    try { $c = Get-Content -LiteralPath $Choices -Raw | ConvertFrom-Json } catch { return 0 }
    $what = [string]$c.when_done
    if ($what -ne "sleep" -and $what -ne "shutdown") { return 0 }
    $verb = "go to sleep"
    if ($what -eq "shutdown") { $verb = "shut down (programs with unsaved work are closed)" }
    $u = Build-EndWindow $verb
    $form = $u.form
    $form.TopMost = $true
    $left = 60
    $msg = $u.msg
    $go = $u.go
    $cancel = $u.cancel
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
        & shutdown.exe /s /f /t 0                       # /f: an open Notepad must not hold it up all night
    } else {
        [void][System.Windows.Forms.Application]::SetSuspendState([System.Windows.Forms.PowerState]::Suspend, $false, $false)
    }
    return 0
}

if ($Mode -eq "layout") { return }

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
