$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m PyInstaller --noconfirm --clean `
  --distpath "dist\DeveloperAuthorizer" `
  --workpath "build\DeveloperAuthorizer" `
  "DeveloperAuthorizer.spec"

Write-Host "Developer authorizer built at dist\DeveloperAuthorizer\DeveloperAuthorizer.exe"


