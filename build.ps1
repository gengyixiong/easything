$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE) { throw 'Python environment creation failed' }
}
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE) { throw 'Dependency installation failed' }
& $python -m PyInstaller --noconfirm --distpath build/frozen --workpath build/pyinstaller packaging/EasyThing.spec
if ($LASTEXITCODE) { throw 'Executable packaging failed' }
# Collect dependency notices alongside the replaceable shared libraries.
& $python packaging/licenses.py build/frozen/EasyThing
if ($LASTEXITCODE) { throw 'License collection failed' }
$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path -LiteralPath $iscc)) { throw 'Install Inno Setup 6 to build EasyThing-Setup.exe' }
& $iscc packaging/installer.iss
if ($LASTEXITCODE) { throw 'Installer build failed' }
Write-Output 'Built dist\EasyThing-Setup.exe'
