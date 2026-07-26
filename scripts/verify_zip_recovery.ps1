[CmdletBinding()]
param(
    [string]$Root = "",
    [string]$PythonExecutable = "",
    [string]$GitleaksPath = ""
)

$ErrorActionPreference = "Stop"
if (-not $Root) {
    $Root = Split-Path -Parent $PSScriptRoot
}
$Root = [System.IO.Path]::GetFullPath($Root)
if (-not $PythonExecutable) {
    $PythonExecutable = Join-Path $Root ".recovery\venv\Scripts\python.exe"
}
if (-not $GitleaksPath) {
    $lock = Get-Content -Raw -LiteralPath (Join-Path $Root "recovery\toolchain.lock.json") | ConvertFrom-Json
    $GitleaksPath = Join-Path $Root ".recovery\tools\gitleaks-$($lock.gitleaks.version)\gitleaks.exe"
}

$VerificationRoot = [System.IO.Path]::GetFullPath((Join-Path $Root ".recovery\zip-contract-verification"))
$AllowedRoot = [System.IO.Path]::GetFullPath((Join-Path $Root ".recovery"))
if (-not $VerificationRoot.StartsWith($AllowedRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "ZIP 合同验证目录越界。"
}
if (Test-Path -LiteralPath $VerificationRoot) {
    Remove-Item -LiteralPath $VerificationRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $VerificationRoot | Out-Null

$manifestPath = Join-Path $Root "recovery\source-manifest.json"
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
foreach ($entry in $manifest.files) {
    $source = Join-Path $Root ([string]$entry.path)
    $destination = Join-Path $VerificationRoot ([string]$entry.path)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination
}
New-Item -ItemType Directory -Force -Path (Join-Path $VerificationRoot "recovery") | Out-Null
Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $VerificationRoot "recovery\source-manifest.json")

if (Test-Path -LiteralPath (Join-Path $VerificationRoot ".git")) {
    throw "ZIP 合同验证目录错误地包含 Git 元数据。"
}

$poisonRoot = Join-Path $AllowedRoot "no-git"
New-Item -ItemType Directory -Force -Path $poisonRoot | Out-Null
Set-Content -LiteralPath (Join-Path $poisonRoot "git.cmd") -Encoding ASCII -Value "@echo Git is forbidden during recovery.& exit /b 97"
$originalPath = $env:PATH
try {
    $env:PATH = "$poisonRoot;$originalPath"
    & (Join-Path $VerificationRoot "scripts\scan_public_tree.ps1") -Root $VerificationRoot -GitleaksPath $GitleaksPath -StrictArchive
    if ($LASTEXITCODE -ne 0) {
        throw "无 Git 的 ZIP 安全扫描失败。"
    }
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExecutable -m unittest discover -s (Join-Path $VerificationRoot "tests") -t $VerificationRoot -v
    if ($LASTEXITCODE -ne 0) {
        throw "无 Git 的 ZIP 自动测试失败。"
    }
} finally {
    $env:PATH = $originalPath
}

Write-Host "无 Git 的 ZIP 合同验证通过。"
