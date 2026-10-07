param([switch]$Verify)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot 'build\pyinstaller-cache'
$pythonExe = Join-Path $PSScriptRoot '.venv-mode3\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { $pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Run the development setup in README.md first.' }
$env:TEMP = Join-Path $PSScriptRoot 'work\test-temp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
# Reuse the complete Tcl/Tk runtime retained in this working copy.
if ($pythonExe -like '*\.venv-mode3\*' -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'work\tcl313\tcl8.6\init.tcl'))) {
    $env:TCL_LIBRARY = Join-Path $PSScriptRoot 'work\tcl313\tcl8.6'
    $env:TK_LIBRARY = Join-Path $PSScriptRoot 'work\tcl313\tk8.6'
} elseif (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'work\tcl\tcl8.6\init.tcl')) {
    $env:TCL_LIBRARY = Join-Path $PSScriptRoot 'work\tcl\tcl8.6'
    $env:TK_LIBRARY = Join-Path $PSScriptRoot 'work\tcl\tk8.6'
}
& $pythonExe -c "import tkinter; tkinter.Tcl()"
if ($LASTEXITCODE -ne 0) { throw 'Tcl/Tk is not accessible. Build with access to the complete GUI runtime.' }
$buildArguments = @(
    '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
    '--name', '网页摘录', '--icon', 'assets/app.ico',
    '--add-data', 'assets/app.ico;assets',
    '--add-data', '第三方许可说明.txt;.',
    '--collect-data', 'trafilatura', '--collect-data', 'justext',
    '--collect-data', 'dateparser', '--collect-data', 'htmldate',
    '--collect-data', 'tld', '--collect-data', 'babel',
    '--copy-metadata', 'trafilatura', '--copy-metadata', 'requests',
    '--exclude-module', 'numpy', '--exclude-module', 'pandas',
    '--exclude-module', 'scipy', '--exclude-module', 'matplotlib',
    '--exclude-module', 'IPython', '--exclude-module', 'pytest',
    '--exclude-module', 'PIL', '--exclude-module', 'PyQt5',
    '--exclude-module', 'PyQt6', '--exclude-module', 'PySide6',
    '--exclude-module', 'cryptography', '--exclude-module', 'OpenSSL',
    'main.py'
)
& $pythonExe @buildArguments
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'dist\网页摘录.exe') -Destination (Join-Path $PSScriptRoot '网页摘录.exe') -Force
Write-Output 'Standalone executable created.'
if ($Verify) {
    $testArguments = @('--self-test', 'verification-exe.json', '--smoke-ui', '--test-url', 'https://www.news.cn/tech/20260929/4a6dd5725b0143c19ef4bdca7742f9d6/c.html')
    $testProcess = Start-Process -FilePath (Join-Path $PSScriptRoot '网页摘录.exe') -WorkingDirectory $PSScriptRoot -ArgumentList $testArguments -WindowStyle Hidden -PassThru -Wait
    if ($testProcess.ExitCode -ne 0) { throw 'Standalone EXE verification failed. See verification-exe.json.' }
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'verification-exe.json') -Encoding UTF8
}
