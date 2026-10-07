param([string]$Action = 'shot', [int]$X = 0, [int]$Y = 0,
      [string]$Text = '', [string]$Path = 'work\mode3-desktop.png', [string]$StepsPath = '')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Mode3Desktop {
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint x, uint y, uint data, UIntPtr extra);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr handle);
    [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr handle, int command);
    [StructLayout(LayoutKind.Sequential)] public struct INPUT { public uint type; public INPUTUNION data; }
    [StructLayout(LayoutKind.Explicit)] public struct INPUTUNION {
        [FieldOffset(0)] public KEYBDINPUT keyboard;
        [FieldOffset(0)] public MOUSEINPUT mouse;
    }
    [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT {
        public ushort key, scan; public uint flags, time; public UIntPtr extra;
    }
    [StructLayout(LayoutKind.Sequential)] public struct MOUSEINPUT {
        public int x, y; public uint data, flags, time; public UIntPtr extra;
    }
    [DllImport("user32.dll")] public static extern uint SendInput(uint count, INPUT[] inputs, int size);
    public static void SendText(string text) {
        foreach (char c in text) {
            INPUT down = new INPUT { type = 1, data = new INPUTUNION { keyboard = new KEYBDINPUT { scan = c, flags = 4 } } };
            INPUT up = new INPUT { type = 1, data = new INPUTUNION { keyboard = new KEYBDINPUT { scan = c, flags = 6 } } };
            SendInput(2, new INPUT[] { down, up }, Marshal.SizeOf(typeof(INPUT)));
        }
    }
}
'@
[Mode3Desktop]::SetProcessDPIAware() | Out-Null
$appProcess = Get-Process | Where-Object { $_.Path -like (Join-Path $PWD '*.exe') -and $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if ($appProcess) {
    [Mode3Desktop]::ShowWindowAsync($appProcess.MainWindowHandle, 9) | Out-Null
    [Mode3Desktop]::SetForegroundWindow($appProcess.MainWindowHandle) | Out-Null
    Start-Sleep -Milliseconds 150
}
function Invoke-DesktopAction($Action, $X, $Y, $Text) {
if ($Action -eq 'click') {
    [Mode3Desktop]::SetCursorPos($X, $Y) | Out-Null
    [Mode3Desktop]::mouse_event(2, 0, 0, 0, [UIntPtr]::Zero)
    [Mode3Desktop]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero)
} elseif ($Action -eq 'type') {
    [System.Windows.Forms.SendKeys]::SendWait($Text)
} elseif ($Action -eq 'text') {
    [Mode3Desktop]::SendText($Text)
} elseif ($Action -eq 'focus') {
    $appProcess = Get-Process | Where-Object { $_.Path -like (Join-Path $PWD '*.exe') -and $_.MainWindowHandle -ne 0 } | Select-Object -First 1
    [Mode3Desktop]::ShowWindowAsync($appProcess.MainWindowHandle, 9) | Out-Null
    [Mode3Desktop]::SetForegroundWindow($appProcess.MainWindowHandle) | Out-Null
} elseif ($Action -ne 'shot') {
    throw 'Unknown desktop action.'
}
Start-Sleep -Milliseconds 300
}
if ($StepsPath) {
    $steps = Get-Content -LiteralPath $StepsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($step in $steps) { Invoke-DesktopAction $step.action $step.x $step.y $step.text }
} else {
    Invoke-DesktopAction $Action $X $Y $Text
}
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bitmap.Save((Join-Path $PWD $Path), [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}
Write-Output $Path
