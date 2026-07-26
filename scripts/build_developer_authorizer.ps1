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

& $PythonExecutable -m PyInstaller --noconfirm --clean `
  --distpath "dist\DeveloperAuthorizerTk" `
  --workpath "build\DeveloperAuthorizerTk" `
  "DingFengDeveloperAuthorizer.spec"
if ($LASTEXITCODE -ne 0) {
  throw "Developer authorizer build failed."
}

Write-Host "Developer authorizer built at dist\DeveloperAuthorizerTk\DingFengDeveloperAuthorizer.exe"
