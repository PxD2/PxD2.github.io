# PXD Web for Windows: .pxd names work in every browser and app on this PC, like .com.
#   on      start the PXD root here (at every boot) and send only .pxd / .pxd2 lookups to it
#   off     stop it and remove the .pxd rule; nothing else on the PC was ever changed
#   status  is it running, and does a test name answer
# Only .pxd and .pxd2 go to the PXD root (a Windows "name resolution policy" rule). Every other name keeps using
# your normal DNS, so turning PXD Web on or off can never break the rest of the internet.
param([ValidateSet("on", "off", "status", "install")][string]$Mode = "status")
$ErrorActionPreference = "Stop"
$Home_ = Join-Path $env:ProgramData "PXD Web"
$Task = "PXD Web"
$Spaces = ".pxd", ".pxd2"

function Say($t, $c = "Gray") { Write-Host $t -ForegroundColor $c }

function Find-Python {
    foreach ($c in @("py -3", "python")) {
        try {
            $exe = & ([scriptblock]::Create("$c -c `"import sys;print(sys.executable)`"")) 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path $exe)) { return $exe.Trim() }
        } catch {}
    }
    return $null
}

function Source-Root {
    # The downloaded package (windows\ next to names.json) or the PXD2 site repo (tools\pxdweb\windows).
    $up1 = (Get-Item $PSScriptRoot).Parent.FullName
    if (Test-Path (Join-Path $up1 "names.json")) { return $up1 }
    $up3 = (Get-Item $PSScriptRoot).Parent.Parent.Parent.FullName
    if (Test-Path (Join-Path $up3 "names.json")) { return $up3 }
    return $null
}

function Install-Files {
    $src = Source-Root
    if (-not $src -or ((Resolve-Path $src).Path -eq (Resolve-Path $Home_ -ErrorAction SilentlyContinue).Path)) { return }
    foreach ($d in "tools\pxd2root", "tools\pxdz", "pxd", "windows") { New-Item -ItemType Directory -Force -Path (Join-Path $Home_ $d) | Out-Null }
    Copy-Item -Force (Join-Path $src "tools\pxd2root\pxd2root.py") (Join-Path $Home_ "tools\pxd2root\")
    Copy-Item -Force (Join-Path $src "tools\pxdz\pxdsign.py") (Join-Path $Home_ "tools\pxdz\")
    Copy-Item -Force (Join-Path $src "names.json") $Home_          # offline fallback copy of the registry
    if (Test-Path (Join-Path $src "names.json.sig")) { Copy-Item -Force (Join-Path $src "names.json.sig") $Home_ }
    if (Test-Path (Join-Path $src "pxd\authority.json")) { Copy-Item -Force (Join-Path $src "pxd\authority.json") (Join-Path $Home_ "pxd\") }
    Copy-Item -Force (Join-Path $PSScriptRoot "*") (Join-Path $Home_ "windows\")
}

function Make-Shortcuts {
    $desk = [Environment]::GetFolderPath("CommonDesktopDirectory"); $sh = New-Object -ComObject WScript.Shell
    $bat = Join-Path $Home_ "windows\PXD Web.bat"
    foreach ($m in "ON", "OFF", "STATUS") {
        $l = $sh.CreateShortcut((Join-Path $desk "PXD Web $m.lnk")); $l.TargetPath = $bat; $l.Arguments = $m.ToLower()
        $l.WorkingDirectory = Join-Path $Home_ "windows"; $l.IconLocation = "shell32.dll,13"; $l.Save()
    }
    $src = Source-Root
    $minter = if ($src) { Join-Path $src "tools\minter\Run_Minter.bat" } else { $null }
    if ($minter -and (Test-Path $minter)) {          # only on a PXD2 machine with the site repo (base1)
        $l = $sh.CreateShortcut((Join-Path $desk "PXD Minter.lnk")); $l.TargetPath = $minter
        $l.WorkingDirectory = Split-Path $minter; $l.IconLocation = "shell32.dll,44"; $l.Save()
    }
}

function Test-Name {
    try { $r = Resolve-DnsName -Name "pxd2.pxd" -Server 127.0.0.1 -Type A -DnsOnly -QuickTimeout -ErrorAction Stop; return [bool]$r } catch { return $false }
}

if ($Mode -eq "install") { Install-Files; Make-Shortcuts; Say "PXD Web installed. Desktop icons: PXD Web ON, OFF, STATUS." Green; $Mode = "on" }

switch ($Mode) {
    "on" {
        $py = Find-Python
        if (-not $py) {
            Say "Python 3 is needed once. Installing it from Microsoft's package manager..." Yellow
            winget install -e --id Python.Python.3.12 --scope machine --accept-package-agreements --accept-source-agreements | Out-Null
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
            $py = Find-Python
            if (-not $py) { Say "Python did not install. Install Python 3 from python.org, then run PXD Web ON again." Red; exit 1 }
        }
        & $py -c "import cryptography" 2>$null
        if ($LASTEXITCODE -ne 0) { & $py -m pip install --quiet cryptography | Out-Null }
        Install-Files
        $pyw = $py -replace 'python\.exe$', 'pythonw.exe'
        if (-not (Test-Path $pyw)) { $pyw = $py }
        $root = Join-Path $Home_ "tools\pxd2root\pxd2root.py"
        $auth = Join-Path $Home_ "pxd\authority.json"
        $args_ = "`"$root`" --host 127.0.0.1 --dns-port 53 --web-port 80 --edge-ip 127.0.0.1 --ns-ip 127.0.0.1 --serve-pages"
        if (Test-Path $auth) { $args_ += " --authority `"$auth`"" }
        # Port 53 or 80 already taken on this PC? Say so plainly instead of failing quietly.
        foreach ($port in 53, 80) {
            $busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalAddress -in "0.0.0.0", "127.0.0.1", "::" }
            if ($busy) {
                $who = (Get-Process -Id $busy[0].OwningProcess -ErrorAction SilentlyContinue).ProcessName
                if ($who -notmatch "python") { Say "Port $port is already used by '$who' on this PC. PXD Web needs it; close that program and try again." Red; exit 1 }
            }
        }
        $action = New-ScheduledTaskAction -Execute $pyw -Argument $args_ -WorkingDirectory $Home_
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
        $who = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        Register-ScheduledTask -TaskName $Task -Action $action -Trigger $trigger -Settings $set -Principal $who -Force | Out-Null
        Stop-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
        Start-ScheduledTask -TaskName $Task
        foreach ($ns in $Spaces) {
            Get-DnsClientNrptRule | Where-Object { $_.Namespace -contains $ns } | ForEach-Object { Remove-DnsClientNrptRule -Name $_.Name -Force }
            Add-DnsClientNrptRule -Namespace $ns -NameServers "127.0.0.1" -Comment "PXD Web" | Out-Null
        }
        Clear-DnsClientCache
        $ok = $false
        foreach ($i in 1..20) { Start-Sleep -Milliseconds 500; if (Test-Name) { $ok = $true; break } }
        if ($ok) {
            Say "PXD Web is ON. .pxd names now work in every browser on this PC." Green
            Say "Type the name with a slash at the end the first time, like  bearwallow.pxd/  (browsers learn .pxd after that)."
            Start-Process "http://pxd2.pxd/"
        } else {
            Say "PXD Web started but pxd2.pxd did not answer yet. Give it a minute, then run PXD Web STATUS." Yellow
        }
    }
    "off" {
        foreach ($ns in $Spaces) {
            Get-DnsClientNrptRule | Where-Object { $_.Namespace -contains $ns } | ForEach-Object { Remove-DnsClientNrptRule -Name $_.Name -Force }
        }
        Stop-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $Task -Confirm:$false -ErrorAction SilentlyContinue
        Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match "pxd2root\.py" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Clear-DnsClientCache
        Say "PXD Web is OFF. This PC is back to plain DNS for everything." Green
    }
    "status" {
        $t = Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
        $rules = Get-DnsClientNrptRule | Where-Object { $_.Comment -eq "PXD Web" }
        Say ("Service:   " + $(if ($t) { $t.State } else { "not installed" }))
        Say ("Rules:     " + $(if ($rules) { ($rules.Namespace -join ", ") + " -> 127.0.0.1" } else { "none" }))
        if (Test-Name) { Say "Test:      pxd2.pxd answers. PXD Web is working." Green } else { Say "Test:      pxd2.pxd does not answer." Yellow }
        try { $s = Invoke-RestMethod "http://127.0.0.1/status" -TimeoutSec 3; Say ("Registry:  " + $s.names + " names, " + $s.registry.state + ", from " + $s.registry.source) } catch {}
    }
}
