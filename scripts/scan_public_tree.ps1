[CmdletBinding()]
param(
    [string]$Root = "",
    [string]$GitleaksPath = "",
    [switch]$SkipGitleaks,
    [switch]$IntegrityOnly,
    [switch]$StrictArchive
)

$ErrorActionPreference = "Stop"
if (-not $Root) {
    $Root = Split-Path -Parent $PSScriptRoot
}
$Root = [System.IO.Path]::GetFullPath($Root)
$ManifestPath = Join-Path $Root "recovery\source-manifest.json"
$PolicyPath = Join-Path $Root "recovery\security-policy.json"

function Get-RelativeUnixPath {
    param([string]$Path)
    $rootWithSeparator = $Root.TrimEnd("\") + "\"
    if (-not $Path.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "路径越出项目根目录：$Path"
    }
    return $Path.Substring($rootWithSeparator.Length).Replace("\", "/")
}

function Get-Sha256 {
    param([string]$Path)
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw "缺少公开源码清单：$ManifestPath"
}

$manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
if ($manifest.schema -ne 1 -or -not $manifest.files) {
    throw "公开源码清单格式无效。"
}

$expected = @{}
foreach ($entry in $manifest.files) {
    $relative = ([string]$entry.path).Replace("\", "/")
    if ($relative.StartsWith("/") -or $relative.Contains("../") -or $expected.ContainsKey($relative)) {
        throw "公开源码清单包含无效或重复路径：$relative"
    }
    $fullPath = [System.IO.Path]::GetFullPath((Join-Path $Root $relative))
    if (-not $fullPath.StartsWith($Root.TrimEnd("\") + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "公开源码清单路径越界：$relative"
    }
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "公开源码缺失：$relative"
    }
    $item = Get-Item -LiteralPath $fullPath
    if ([int64]$entry.size -ne $item.Length) {
        throw "公开源码大小不符：$relative"
    }
    $actualHash = Get-Sha256 -Path $fullPath
    if ($actualHash -ne ([string]$entry.sha256).ToLowerInvariant()) {
        throw "公开源码摘要不符：$relative"
    }
    $expected[$relative] = $fullPath
}

if ($StrictArchive) {
    $actual = Get-ChildItem -LiteralPath $Root -Recurse -Force -File |
        Where-Object {
            $_.FullName -notlike "$Root\.git\*" -and
            $_.FullName -notlike "$Root\.recovery\*" -and
            $_.FullName -notlike "$Root\build\*" -and
            $_.FullName -notlike "$Root\dist\*" -and
            $_.FullName -notlike "$Root\electron\node_modules\*" -and
            $_.FullName -notlike "$Root\recovery\source-manifest.json"
        }
    foreach ($item in $actual) {
        $relative = Get-RelativeUnixPath -Path $item.FullName
        if (-not $expected.ContainsKey($relative)) {
            throw "ZIP 中存在源码清单之外的文件：$relative"
        }
    }
}

if ($IntegrityOnly) {
    Write-Host ("源码清单完整性通过：{0} 个文件。" -f $expected.Count)
    exit 0
}

$policy = Get-Content -Raw -LiteralPath $PolicyPath | ConvertFrom-Json
$textExtensions = @(
    ".cmd", ".css", ".html", ".ini", ".js", ".json", ".md", ".ps1",
    ".py", ".spec", ".toml", ".txt", ".xml", ".yaml", ".yml"
)

foreach ($relative in ($expected.Keys | Sort-Object)) {
    foreach ($pattern in $policy.forbiddenPathPatterns) {
        if ($relative -match $pattern) {
            throw "公开源码含禁止路径：$relative"
        }
    }

    $fullPath = $expected[$relative]
    $extension = [System.IO.Path]::GetExtension($fullPath).ToLowerInvariant()
    if ($textExtensions -notcontains $extension) {
        continue
    }
    if ((Get-Item -LiteralPath $fullPath).Length -gt 10MB) {
        continue
    }
    $content = Get-Content -Raw -LiteralPath $fullPath -ErrorAction Stop
    foreach ($pattern in $policy.forbiddenContentPatterns) {
        if ($content -match $pattern) {
            throw "公开源码内容触发秘密或本机路径规则：$relative"
        }
    }
    if ($extension -eq ".md" -and $content -match $policy.documentationPhonePattern) {
        throw "公开文档含疑似电话号码：$relative"
    }
}

$reportsRoot = Join-Path $Root ".recovery\reports"
New-Item -ItemType Directory -Force -Path $reportsRoot | Out-Null

if (-not $SkipGitleaks) {
    if (-not $GitleaksPath -or -not (Test-Path -LiteralPath $GitleaksPath -PathType Leaf)) {
        throw "未提供可执行的 Gitleaks 秘密扫描器。"
    }

    $scanRoot = [System.IO.Path]::GetFullPath((Join-Path $Root ".recovery\security-scan-tree"))
    $allowedGeneratedRoot = [System.IO.Path]::GetFullPath((Join-Path $Root ".recovery"))
    if (-not $scanRoot.StartsWith($allowedGeneratedRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "安全扫描临时目录越界。"
    }
    if (Test-Path -LiteralPath $scanRoot) {
        Remove-Item -LiteralPath $scanRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $scanRoot | Out-Null
    foreach ($relative in $expected.Keys) {
        $destination = Join-Path $scanRoot $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $expected[$relative] -Destination $destination
    }

    $gitleaksReport = Join-Path $reportsRoot "gitleaks.json"
    & $GitleaksPath dir $scanRoot --no-banner --redact --config (Join-Path $Root "recovery\gitleaks.toml") --report-format json --report-path $gitleaksReport
    if ($LASTEXITCODE -ne 0) {
        throw "Gitleaks 秘密扫描发现问题，报告：$gitleaksReport"
    }
}

$summary = [ordered]@{
    schema = 1
    scannedAt = [DateTimeOffset]::Now.ToString("o")
    files = $expected.Count
    sourceManifest = "passed"
    policyScan = "passed"
    gitleaks = if ($SkipGitleaks) { "skipped" } else { "passed" }
    gitMetadataRequired = $false
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $reportsRoot "安全扫描报告.json") -Encoding UTF8
Write-Host ("公开源码安全扫描通过：{0} 个文件；不依赖 .git。" -f $expected.Count)
exit 0
