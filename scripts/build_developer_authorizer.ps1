$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -c "import cryptography; print('cryptography dependency ready')"

python -m PyInstaller --noconfirm --clean `
  --distpath "dist\DeveloperAuthorizerTk" `
  --workpath "build\DeveloperAuthorizerTk" `
  "DingFengDeveloperAuthorizer.spec"

Write-Host "Developer authorizer built at dist\DeveloperAuthorizerTk\DingFengDeveloperAuthorizer.exe"
