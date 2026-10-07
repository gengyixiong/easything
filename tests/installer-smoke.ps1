# Uses only EasyThing's app data. Run before using the app with personal folders.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$dataRoot = Join-Path $env:LOCALAPPDATA 'EasyThing'
$settingsFile = Join-Path $dataRoot 'settings\settings.json'
if (Test-Path -LiteralPath $settingsFile) {
    throw 'Existing user settings found; do not replace them during installer smoke testing.'
}
$installDir = Join-Path (Get-Location).Path ('build\installed-smoke-' + [guid]::NewGuid().ToString('N'))
$sourceDir = Join-Path (Get-Location).Path 'build\original-documents-smoke'
New-Item -ItemType Directory -Force -Path $sourceDir | Out-Null
$original = Join-Path $sourceDir 'original.md'
'This original document must survive uninstall.' | Set-Content -LiteralPath $original
$originalHash = (Get-FileHash -LiteralPath $original).Hash
$installer = (Resolve-Path -LiteralPath 'dist\EasyThing-Setup.exe').Path
$arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/DIR="' + $installDir + '"'))
$process = Start-Process -FilePath $installer -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Installer failed' }
if (-not (Test-Path -LiteralPath (Join-Path $installDir 'EasyThing.exe'))) { throw 'Executable was not installed' }
foreach ($name in @('models', 'index', 'settings', 'cache')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $dataRoot $name) | Out-Null
    'preserve by default' | Set-Content -LiteralPath (Join-Path $dataRoot "$name\installer-smoke-marker.txt")
}
# Include an original document path in settings, proving cleanup never follows it.
@{ folders = @(@{ path = $sourceDir; enabled = $true; recursive = $true }) } |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $settingsFile -Encoding utf8
$uninstaller = Join-Path $installDir 'unins000.exe'
$process = Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Default uninstall failed' }
foreach ($name in @('models', 'index', 'settings', 'cache')) {
    if (-not (Test-Path -LiteralPath (Join-Path $dataRoot "$name\installer-smoke-marker.txt"))) { throw "Default uninstall deleted $name" }
}
if ((Get-FileHash -LiteralPath $original).Hash -ne $originalHash) { throw 'Original file changed' }
Write-Output 'PASS: installation and default uninstall preserve model, index, settings, cache and original documents.'
$process = Start-Process -FilePath $installer -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Reinstall failed' }
$process = Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/DELETEMODEL', '/DELETEINDEX', '/DELETESETTINGS' -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Cleanup uninstall failed' }
foreach ($name in @('models', 'index', 'settings', 'cache')) {
    if (Test-Path -LiteralPath (Join-Path $dataRoot $name)) { throw "Cleanup did not remove $name" }
}
if ((Get-FileHash -LiteralPath $original).Hash -ne $originalHash) { throw 'Original document was changed or deleted' }
Write-Output 'PASS: explicit cleanup removes only selected EasyThing data; original document survives.'
