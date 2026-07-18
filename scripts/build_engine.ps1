$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -c "import cryptography; print('cryptography dependency ready')"

$workspaceRoot = Split-Path -Parent $root
$genderMapSource = Get-ChildItem -LiteralPath $workspaceRoot -Recurse -Filter "_gender_map.js" -File |
  Where-Object { $_.FullName -notlike "$root*" -and $_.Length -gt 1000000 } |
  Select-Object -First 1 -ExpandProperty FullName
$genderMapTargetDir = Join-Path $root ".tmp_build_assets\gender"
$genderMapTarget = Join-Path $genderMapTargetDir "_gender_map.js"
if ($genderMapSource -and (Test-Path -LiteralPath $genderMapSource)) {
  New-Item -ItemType Directory -Force -Path $genderMapTargetDir | Out-Null
  Copy-Item -LiteralPath $genderMapSource -Destination $genderMapTarget -Force
} elseif (Test-Path -LiteralPath $genderMapTarget) {
  Write-Host "Using existing gender map asset at $genderMapTarget"
} else {
  throw "Missing gender map asset: $genderMapSource"
}

python -m PyInstaller --noconfirm --clean `
  --distpath "dist" `
  --workpath "build\DingFengEngine" `
  "DingFengEngine.spec"

Write-Host "Engine built at dist\DingFengEngine\dingfeng_engine.exe"
