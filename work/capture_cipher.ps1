param([long]$WindowHandle, [string]$OutputPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class CipherCapture {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr dc, uint flags);
    [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr hwnd);
}
'@
$captureHandle = [CipherCapture]::GetParent([IntPtr]$WindowHandle)
$captureRect = New-Object CipherCapture+RECT
[CipherCapture]::GetWindowRect($captureHandle, [ref]$captureRect) | Out-Null
$bitmap = New-Object System.Drawing.Bitmap ($captureRect.Right - $captureRect.Left), ($captureRect.Bottom - $captureRect.Top)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $captureDc = $graphics.GetHdc()
    try { $captured = [CipherCapture]::PrintWindow($captureHandle, $captureDc, 0) }
    finally { $graphics.ReleaseHdc($captureDc) }
    if (-not $captured) { throw 'PrintWindow failed.' }
    $bitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}
