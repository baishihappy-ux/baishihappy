[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PythonExecutable,
    [Parameter(Mandatory = $true)]
    [string]$NodeExecutable
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PythonExecutable = [System.IO.Path]::GetFullPath($PythonExecutable)
$NodeExecutable = [System.IO.Path]::GetFullPath($NodeExecutable)

if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    throw "Python 构建解释器不存在：$PythonExecutable"
}
if (-not (Test-Path -LiteralPath $NodeExecutable -PathType Leaf)) {
    throw "Node.js 构建解释器不存在：$NodeExecutable"
}

& (Join-Path $PSScriptRoot "build_developer_authorizer.ps1") -PythonExecutable $PythonExecutable
if ($LASTEXITCODE -ne 0) {
    throw "开发者授权器构建失败。"
}

& (Join-Path $PSScriptRoot "build_engine.ps1") -PythonExecutable $PythonExecutable
if ($LASTEXITCODE -ne 0) {
    throw "生产引擎构建失败。"
}

$ValidationRoot = [System.IO.Path]::GetFullPath((Join-Path $Root "dist\restore-validation"))
$DistRoot = [System.IO.Path]::GetFullPath((Join-Path $Root "dist"))
if (-not $ValidationRoot.StartsWith($DistRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "验证构建目录越界。"
}
if (Test-Path -LiteralPath $ValidationRoot) {
    Remove-Item -LiteralPath $ValidationRoot -Recurse -Force
}

$StageRoot = Join-Path $Root ".recovery\production-app-stage"
$RecoveryRoot = [System.IO.Path]::GetFullPath((Join-Path $Root ".recovery"))
$StageRoot = [System.IO.Path]::GetFullPath($StageRoot)
if (-not $StageRoot.StartsWith($RecoveryRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "应用暂存目录越界。"
}
if (Test-Path -LiteralPath $StageRoot) {
    Remove-Item -LiteralPath $StageRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $StageRoot, $ValidationRoot | Out-Null

$package = [ordered]@{
    name = "workspace-production-client"
    version = "9.1.2"
    main = "main.js"
}
$package | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $StageRoot "package.json") -Encoding UTF8
Copy-Item -LiteralPath (Join-Path $Root "electron\main.js") -Destination $StageRoot
Copy-Item -LiteralPath (Join-Path $Root "electron\preload.js") -Destination $StageRoot
Copy-Item -LiteralPath (Join-Path $Root "electron\renderer") -Destination $StageRoot -Recurse
Copy-Item -LiteralPath (Join-Path $Root "electron\monitor") -Destination $StageRoot -Recurse

$AsarCli = Join-Path $Root "electron\node_modules\@electron\asar\bin\asar.mjs"
if (-not (Test-Path -LiteralPath $AsarCli -PathType Leaf)) {
    throw "缺少固定版本的 ASAR 打包工具。"
}

$CustomerRoot = Join-Path $ValidationRoot "customer-package"
$CustomerApp = Join-Path $CustomerRoot "app"
$ElectronDist = Join-Path $Root "electron\node_modules\electron\dist"
if (-not (Test-Path -LiteralPath (Join-Path $ElectronDist "electron.exe") -PathType Leaf)) {
    throw "Electron 运行时不完整。"
}
New-Item -ItemType Directory -Force -Path $CustomerApp | Out-Null
Copy-Item -Path (Join-Path $ElectronDist "*") -Destination $CustomerApp -Recurse -Force

$originalExe = Join-Path $CustomerApp "electron.exe"
$validationExe = Join-Path $CustomerApp "WorkspaceProductionValidation.exe"
Move-Item -LiteralPath $originalExe -Destination $validationExe

$resources = Join-Path $CustomerApp "resources"
& $NodeExecutable $AsarCli pack $StageRoot (Join-Path $resources "app.asar")
if ($LASTEXITCODE -ne 0) {
    throw "客户壳 app.asar 构建失败。"
}

$engineSource = Join-Path $Root "dist\DingFengEngine"
$engineTarget = Join-Path $resources "engine"
Copy-Item -LiteralPath $engineSource -Destination $engineTarget -Recurse
$defaultConfig = Join-Path $resources "default_config"
New-Item -ItemType Directory -Force -Path $defaultConfig | Out-Null
Copy-Item -LiteralPath (Join-Path $Root "runtime\config\app_config.json") -Destination $defaultConfig

foreach ($directory in @("config", "logs", "output", "cache", "temp", "state")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $CustomerRoot "runtime\$directory") | Out-Null
}

@(
    "THIS DIRECTORY IS A RESTORE VALIDATION BUILD.",
    "NOT FOR CUSTOMER DELIVERY.",
    "NO FORMAL SUITE ID WAS CONSUMED."
) | Set-Content -LiteralPath (Join-Path $CustomerRoot "NOT_FOR_DELIVERY.txt") -Encoding ASCII

$authorizer = Join-Path $Root "dist\DeveloperAuthorizerTk\DingFengDeveloperAuthorizer.exe"
$engineExe = Join-Path $engineTarget "dingfeng_engine.exe"
if (-not (Test-Path -LiteralPath $authorizer -PathType Leaf)) {
    throw "开发者授权器验证产物缺失。"
}
if (-not (Test-Path -LiteralPath $engineExe -PathType Leaf)) {
    throw "客户包生产引擎缺失。"
}

$forbiddenCustomerPaths = Get-ChildItem -LiteralPath $CustomerRoot -Recurse -Force |
    Where-Object {
        $_.Name -match "(?i)(license\.dat|issuer_private|private_key|developer_authorizer|generate_license|\.package-secrets)"
    }
if ($forbiddenCustomerPaths) {
    throw "客户验证包含禁止的授权、私钥或签发文件：$($forbiddenCustomerPaths[0].FullName)"
}

$archiveListing = & $PythonExecutable -m PyInstaller.utils.cliutils.archive_viewer -l $engineExe 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "无法检查生产引擎归档内容。"
}
$listingText = $archiveListing -join "`n"
foreach ($forbidden in @("license_issuer", "windows_dpapi", "developer_authorizer", "generate_license_keypair")) {
    if ($listingText -match [regex]::Escape($forbidden)) {
        throw "客户引擎包含禁止的授权签发模块：$forbidden"
    }
}

$asset = Join-Path $engineTarget "_internal\_gender_map.js"
if (-not (Test-Path -LiteralPath $asset -PathType Leaf)) {
    throw "客户引擎缺少性别映射构建资源。"
}
$assetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $asset).Hash.ToLowerInvariant()
if ($assetHash -ne "20b0122a7be802b95e1c6ccb44854bfb4a55023c672dec0dbae348058a0859dc") {
    throw "客户引擎性别映射摘要不正确。"
}

& $engineExe --help | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "客户引擎命令行启动检查失败。"
}

$artifacts = Get-ChildItem -LiteralPath $ValidationRoot -Recurse -File | ForEach-Object {
    [ordered]@{
        path = $_.FullName.Substring($ValidationRoot.Length + 1).Replace("\", "/")
        size = $_.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
    }
}
$result = [ordered]@{
    schema = 1
    builtAt = [DateTimeOffset]::Now.ToString("o")
    deliverable = $false
    formalSuiteIdConsumed = $false
    developerAuthorizer = $authorizer
    validationCustomerPackage = $CustomerRoot
    artifacts = $artifacts
}
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $ValidationRoot "build-manifest.json") -Encoding UTF8
Write-Host "生产验证构建完成；未生成正式客户包，未消耗套装编号。"
