$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m PyInstaller --noconfirm --clean `
  --distpath "dist" `
  --workpath "build\RuntimeEngine" `
  "RuntimeEngine.spec"

Write-Host "Engine built at dist\RuntimeEngine\runtime_engine.exe"


