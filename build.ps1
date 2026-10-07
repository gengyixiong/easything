$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE) { throw 'Python environment creation failed' }
}
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE) { throw 'Dependency installation failed' }
& $python -m nuitka --mode=standalone --msvc=latest --enable-plugin=pyside6 `
    --include-qt-plugins=sensible --include-package=easything `
    --include-package=win32com.client --include-module=pythoncom --include-module=pywintypes `
    --include-package-data=pptx `
    --user-package-configuration-file=packaging/nuitka.yml `
    --nofollow-import-to=pytest,IPython,matplotlib,pandas,scipy,torch,tensorflow,numba `
    --windows-console-mode=disable --output-filename=EasyThing.exe `
    --output-dir=build --assume-yes-for-downloads --jobs=8 launch.py
if ($LASTEXITCODE) { throw 'Nuitka build failed' }
# Collect dependency notices alongside the replaceable shared libraries.
& $python packaging/licenses.py build/launch.dist
if ($LASTEXITCODE) { throw 'License collection failed' }
$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path -LiteralPath $iscc)) { throw 'Install Inno Setup 6 to build EasyThing-Setup.exe' }
& $iscc packaging/installer.iss
if ($LASTEXITCODE) { throw 'Installer build failed' }
Write-Output 'Built dist\EasyThing-Setup.exe'
