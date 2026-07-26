[CmdletBinding()]
param(
    [string]$Root = ""
)

$ErrorActionPreference = "Stop"
if (-not $Root) {
    $Root = Split-Path -Parent $PSScriptRoot
}
$Root = [System.IO.Path]::GetFullPath($Root)
$ManifestPath = Join-Path $Root "recovery\source-manifest.json"
$GeneratedRoot = [System.IO.Path]::GetFullPath((Join-Path $Root ".recovery\manifest-source"))
$AllowedRoot = [System.IO.Path]::GetFullPath((Join-Path $Root ".recovery"))

if (-not $GeneratedRoot.StartsWith($AllowedRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "维护清单暂存目录越界。"
}

$gitArguments = @("-c", "safe.directory=$Root", "-c", "core.quotepath=false", "-C", $Root)
$treeId = & git @gitArguments write-tree
if ($LASTEXITCODE -ne 0 -or -not $treeId) {
    throw "无法读取已暂存的公开发布树。请先检查并暂存预定公开文件。正式恢复不调用 Git。"
}

if (Test-Path -LiteralPath $GeneratedRoot) {
    Remove-Item -LiteralPath $GeneratedRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $GeneratedRoot | Out-Null
$archivePath = Join-Path $GeneratedRoot "source.zip"
$extractRoot = Join-Path $GeneratedRoot "tree"
New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null

& git @gitArguments archive --format=zip --output=$archivePath $treeId
if ($LASTEXITCODE -ne 0) {
    throw "无法生成已暂存发布树的 ZIP 快照。"
}
Expand-Archive -LiteralPath $archivePath -DestinationPath $extractRoot

$files = @()
foreach ($item in (Get-ChildItem -LiteralPath $extractRoot -Recurse -File | Sort-Object FullName)) {
    $relative = $item.FullName.Substring($extractRoot.Length + 1).Replace("\", "/")
    if ($relative -eq "recovery/source-manifest.json") {
        continue
    }
    $files += [ordered]@{
        path = $relative
        size = $item.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $item.FullName).Hash.ToLowerInvariant()
    }
}

$manifest = [ordered]@{
    schema = 1
    algorithm = "sha256"
    sourceTree = $treeId.ToString().Trim()
    files = $files
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
Write-Host ("已根据暂存发布树更新公开源码清单：{0} 个文件。" -f $files.Count)
