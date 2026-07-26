[CmdletBinding()]
param(
  [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $PythonExecutable) {
  $managedPython = Join-Path $root ".recovery\venv\Scripts\python.exe"
  $PythonExecutable = if (Test-Path -LiteralPath $managedPython) { $managedPython } else { "python.exe" }
}

& $PythonExecutable -c "import cryptography; print('cryptography dependency ready')"
if ($LASTEXITCODE -ne 0) {
  throw "Python cryptography dependency is unavailable."
}

$genderMapSource = Join-Path $root "assets\build\gender\_gender_map.js"
if (-not (Test-Path -LiteralPath $genderMapSource -PathType Leaf)) {
  throw "Missing repository gender map asset: $genderMapSource"
}
$genderMapHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $genderMapSource).Hash.ToLowerInvariant()
if ($genderMapHash -ne "20b0122a7be802b95e1c6ccb44854bfb4a55023c672dec0dbae348058a0859dc") {
  throw "Repository gender map asset hash mismatch: $genderMapHash"
}

& $PythonExecutable -m PyInstaller --noconfirm --clean `
  --distpath "dist" `
  --workpath "build\DingFengEngine" `
  "DingFengEngine.spec"
if ($LASTEXITCODE -ne 0) {
  throw "Engine build failed."
}

Write-Host "Engine built at dist\DingFengEngine\dingfeng_engine.exe"
