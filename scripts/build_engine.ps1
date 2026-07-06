$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m PyInstaller --noconfirm --clean `
  --distpath "dist" `
  --workpath "build\DingFengEngine" `
  "DingFengEngine.spec"

Write-Host "Engine built at dist\DingFengEngine\dingfeng_engine.exe"
