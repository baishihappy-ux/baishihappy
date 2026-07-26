[CmdletBinding()]
param(
    [switch]$NonInteractive,
    [switch]$SkipBuild,
    [switch]$SkipGitleaks,
    [switch]$StrictArchive
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Root = Split-Path -Parent $PSScriptRoot
$RecoveryRoot = Join-Path $Root ".recovery"
$CacheRoot = Join-Path $RecoveryRoot "cache"
$ToolsRoot = Join-Path $RecoveryRoot "tools"
$ReportsRoot = Join-Path $RecoveryRoot "reports"
$ReportJson = Join-Path $ReportsRoot "恢复报告.json"
$ReportText = Join-Path $ReportsRoot "恢复报告.txt"
$Toolchain = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot "toolchain.lock.json") | ConvertFrom-Json
$StartedAt = [DateTimeOffset]::Now
$StageResults = [ordered]@{}
$NpmCache = ""
$ElectronCache = ""

function Write-Stage {
    param([string]$Name, [string]$Message)
    Write-Host ""
    Write-Host ("[{0}] {1}" -f $Name, $Message) -ForegroundColor Cyan
}

function Complete-Stage {
    param([string]$Name, [string]$Detail)
    $StageResults[$Name] = [ordered]@{
        status = "passed"
        detail = $Detail
    }
    Write-Host ("[通过] {0}" -f $Detail) -ForegroundColor Green
}

function Get-Sha256 {
    param([string]$Path)
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Assert-FileHash {
    param([string]$Path, [string]$Expected)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "缺少文件：$Path"
    }
    $actual = Get-Sha256 -Path $Path
    if ($actual -ne $Expected.ToLowerInvariant()) {
        throw "文件摘要不匹配：$Path；预期=$Expected；实际=$actual"
    }
}

function Invoke-VerifiedDownload {
    param(
        [string]$Uri,
        [string]$Destination,
        [string]$Sha256
    )
    if (Test-Path -LiteralPath $Destination -PathType Leaf) {
        try {
            Assert-FileHash -Path $Destination -Expected $Sha256
            return
        } catch {
            Remove-Item -LiteralPath $Destination -Force
        }
    }

    $parent = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $delays = @(0, 2, 5)
    $lastError = $null
    for ($attempt = 0; $attempt -lt $delays.Count; $attempt++) {
        if ($delays[$attempt] -gt 0) {
            Start-Sleep -Seconds $delays[$attempt]
        }
        try {
            Write-Host ("下载：{0}（第 {1}/3 次）" -f $Uri, ($attempt + 1))
            Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $Destination -TimeoutSec 300
            Assert-FileHash -Path $Destination -Expected $Sha256
            return
        } catch {
            $lastError = $_
            if (Test-Path -LiteralPath $Destination) {
                Remove-Item -LiteralPath $Destination -Force
            }
        }
    }
    throw "下载或校验失败：$Uri；$($lastError.Exception.Message)"
}

function Prepare-RecoveryBundle {
    $bundleArchive = Join-Path $CacheRoot $Toolchain.bundle.file
    $bundleHash = [string]$Toolchain.bundle.sha256
    if ($bundleHash) {
        Invoke-VerifiedDownload -Uri $Toolchain.bundle.url -Destination $bundleArchive -Sha256 $bundleHash
    } elseif (-not (Test-Path -LiteralPath $bundleArchive -PathType Leaf)) {
        New-Item -ItemType Directory -Force -Path $CacheRoot | Out-Null
        Write-Host "从本项目 GitHub 发布附件下载固定恢复工具包。"
        Invoke-WebRequest -UseBasicParsing -Uri $Toolchain.bundle.url -OutFile $bundleArchive -TimeoutSec 300
    }

    $bundleRoot = [System.IO.Path]::GetFullPath((Join-Path $RecoveryRoot "bundle"))
    if (Test-Path -LiteralPath $bundleRoot) {
        Remove-Item -LiteralPath $bundleRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $bundleRoot | Out-Null
    Expand-Archive -LiteralPath $bundleArchive -DestinationPath $bundleRoot -Force

    $bundleManifestPath = Join-Path $bundleRoot "bundle-manifest.json"
    if (-not (Test-Path -LiteralPath $bundleManifestPath -PathType Leaf)) {
        throw "恢复工具包缺少内部摘要清单。"
    }
    $bundleManifest = Get-Content -Raw -LiteralPath $bundleManifestPath | ConvertFrom-Json
    foreach ($entry in $bundleManifest.files) {
        $relative = ([string]$entry.path).Replace("/", "\")
        $fullPath = [System.IO.Path]::GetFullPath((Join-Path $bundleRoot $relative))
        if (-not $fullPath.StartsWith($bundleRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "恢复工具包内部路径越界：$relative"
        }
        Assert-FileHash -Path $fullPath -Expected $entry.sha256
    }

    $pythonArchiveName = "python-$($Toolchain.python.version)-amd64.exe"
    $nodeArchiveName = "node-v$($Toolchain.node.version)-win-x64.zip"
    $gitleaksArchiveName = "gitleaks-$($Toolchain.gitleaks.version)-windows-x64.zip"
    $bundleFiles = @(
        @{ source = "downloads\$pythonArchiveName"; target = $pythonArchiveName; hash = $Toolchain.python.sha256 },
        @{ source = "downloads\$nodeArchiveName"; target = $nodeArchiveName; hash = $Toolchain.node.sha256 },
        @{ source = "downloads\$gitleaksArchiveName"; target = $gitleaksArchiveName; hash = $Toolchain.gitleaks.sha256 }
    )
    foreach ($bundleFile in $bundleFiles) {
        $source = Join-Path $bundleRoot $bundleFile.source
        Assert-FileHash -Path $source -Expected $bundleFile.hash
        Copy-Item -LiteralPath $source -Destination (Join-Path $CacheRoot $bundleFile.target) -Force
    }

    $bundleWheelhouse = Join-Path $bundleRoot "wheelhouse"
    if (-not (Test-Path -LiteralPath $bundleWheelhouse -PathType Container)) {
        throw "恢复工具包缺少 Python 离线依赖。"
    }
    $cacheWheelhouse = Join-Path $CacheRoot "wheelhouse"
    if (Test-Path -LiteralPath $cacheWheelhouse) {
        Remove-Item -LiteralPath $cacheWheelhouse -Recurse -Force
    }
    Copy-Item -LiteralPath $bundleWheelhouse -Destination $cacheWheelhouse -Recurse

    $script:NpmCache = Join-Path $bundleRoot "npm-cache"
    $script:ElectronCache = Join-Path $bundleRoot "electron-cache"
    if (-not (Test-Path -LiteralPath $script:NpmCache -PathType Container)) {
        throw "恢复工具包缺少 npm 离线缓存。"
    }
    if (-not (Test-Path -LiteralPath $script:ElectronCache -PathType Container)) {
        throw "恢复工具包缺少 Electron 离线缓存。"
    }
}

function Get-CommandVersion {
    param([string]$Command, [string[]]$Arguments)
    try {
        $output = & $Command @Arguments 2>&1
        if ($LASTEXITCODE -ne 0) {
            return ""
        }
        return (($output | Select-Object -First 1).ToString()).Trim()
    } catch {
        return ""
    }
}

function Resolve-Python {
    $expected = [string]$Toolchain.python.version
    $system = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($system) {
        $version = Get-CommandVersion -Command $system.Source -Arguments @("--version")
        if ($version -eq "Python $expected") {
            return $system.Source
        }
    }

    $pythonRoot = Join-Path $ToolsRoot "python-$expected"
    $pythonExe = Join-Path $pythonRoot "python.exe"
    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
        $installer = Join-Path $CacheRoot ("python-{0}-amd64.exe" -f $expected)
        Invoke-VerifiedDownload -Uri $Toolchain.python.url -Destination $installer -Sha256 $Toolchain.python.sha256
        New-Item -ItemType Directory -Force -Path $pythonRoot | Out-Null
        $arguments = @(
            "/quiet",
            "InstallAllUsers=0",
            "TargetDir=`"$pythonRoot`"",
            "Include_pip=1",
            "Include_launcher=0",
            "Include_test=0",
            "Include_doc=0",
            "AssociateFiles=0",
            "Shortcuts=0",
            "PrependPath=0"
        )
        $process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
        if ($process.ExitCode -ne 0) {
            throw "Python 本地安装失败，退出码：$($process.ExitCode)"
        }
    }
    $version = Get-CommandVersion -Command $pythonExe -Arguments @("--version")
    if ($version -ne "Python $expected") {
        throw "本地 Python 版本不正确：$version"
    }
    return $pythonExe
}

function Resolve-Node {
    $expected = [string]$Toolchain.node.version
    $system = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($system) {
        $version = Get-CommandVersion -Command $system.Source -Arguments @("--version")
        if ($version -eq "v$expected") {
            $npm = Join-Path (Split-Path -Parent $system.Source) "npm.cmd"
            if (Test-Path -LiteralPath $npm -PathType Leaf) {
                return [ordered]@{ node = $system.Source; npm = $npm }
            }
        }
    }

    $archive = Join-Path $CacheRoot ("node-v{0}-win-x64.zip" -f $expected)
    Invoke-VerifiedDownload -Uri $Toolchain.node.url -Destination $archive -Sha256 $Toolchain.node.sha256
    $nodeRoot = Join-Path $ToolsRoot ("node-v{0}-win-x64" -f $expected)
    $nodeExe = Join-Path $nodeRoot "node.exe"
    if (-not (Test-Path -LiteralPath $nodeExe -PathType Leaf)) {
        Expand-Archive -LiteralPath $archive -DestinationPath $ToolsRoot -Force
    }
    $npm = Join-Path $nodeRoot "npm.cmd"
    if (-not (Test-Path -LiteralPath $nodeExe -PathType Leaf) -or -not (Test-Path -LiteralPath $npm -PathType Leaf)) {
        throw "Node.js 本地工具链不完整。"
    }
    return [ordered]@{ node = $nodeExe; npm = $npm }
}

function Resolve-Gitleaks {
    $expected = [string]$Toolchain.gitleaks.version
    $toolRoot = Join-Path $ToolsRoot "gitleaks-$expected"
    $executable = Join-Path $toolRoot "gitleaks.exe"
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        $archive = Join-Path $CacheRoot ("gitleaks-{0}-windows-x64.zip" -f $expected)
        Invoke-VerifiedDownload -Uri $Toolchain.gitleaks.url -Destination $archive -Sha256 $Toolchain.gitleaks.sha256
        New-Item -ItemType Directory -Force -Path $toolRoot | Out-Null
        Expand-Archive -LiteralPath $archive -DestinationPath $toolRoot -Force
    }
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "秘密扫描工具不完整。"
    }
    return $executable
}

function Write-FinalReport {
    param([bool]$Succeeded, [string]$Conclusion, [string]$Failure)
    New-Item -ItemType Directory -Force -Path $ReportsRoot | Out-Null
    $report = [ordered]@{
        schema = 1
        startedAt = $StartedAt.ToString("o")
        completedAt = [DateTimeOffset]::Now.ToString("o")
        succeeded = $Succeeded
        conclusion = $Conclusion
        failure = $Failure
        stages = $StageResults
        formalCustomerPackageGenerated = $false
        authorizationIssuance = if (Test-Path -LiteralPath (Join-Path $Root ".package-secrets\authorization\issuer_private_key.dpapi.json")) { "available-for-current-windows-user" } else { "not-restored-private-key-intentionally-excluded" }
        codeSigning = "not-configured"
    }
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportJson -Encoding UTF8

    $lines = @(
        "灾难恢复报告",
        "完成时间：$($report.completedAt)",
        "结论：$Conclusion",
        "继续开发能力：$(if ($Succeeded) { '具备' } else { '不具备' })",
        "生产构建能力：$(if ($Succeeded -and -not $SkipBuild) { '具备（验证构建通过）' } elseif ($Succeeded) { '未验证（本次跳过构建）' } else { '不具备' })",
        "正式客户包：未生成",
        "授权码签发：$(if ($report.authorizationIssuance -eq 'available-for-current-windows-user') { '本机当前用户私钥存在' } else { '未恢复；私钥按安全规则不进入公开仓库' })",
        "代码签名：未配置"
    )
    if ($Failure) {
        $lines += "失败原因：$Failure"
    }
    $lines | Set-Content -LiteralPath $ReportText -Encoding UTF8
}

try {
    Write-Stage -Name "预检" -Message "检查操作系统、路径、磁盘和源码清单。"
    if (-not [Environment]::Is64BitOperatingSystem) {
        throw "仅支持 64 位 Windows。"
    }
    if ($Root.Length -gt 120) {
        throw "项目根路径超过 120 个字符，请解压到更短的新路径。"
    }
    $drive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($Root).Substring(0, 1))
    if ($drive.Free -lt 10GB) {
        throw "可用磁盘空间不足 10 GiB。"
    }
    & (Join-Path $Root "scripts\scan_public_tree.ps1") -Root $Root -IntegrityOnly -StrictArchive:$StrictArchive
    if ($LASTEXITCODE -ne 0) {
        throw "源码完整性检查失败。"
    }
    Complete-Stage -Name "preflight" -Detail "系统和源码完整性检查通过。"

    Write-Stage -Name "工具" -Message "准备隔离的 Python、Node.js 和秘密扫描工具。"
    New-Item -ItemType Directory -Force -Path $CacheRoot, $ToolsRoot, $ReportsRoot | Out-Null
    Prepare-RecoveryBundle
    $basePython = Resolve-Python
    $nodeTools = Resolve-Node
    $gitleaks = if ($SkipGitleaks) { "" } else { Resolve-Gitleaks }
    Complete-Stage -Name "tools" -Detail "固定版本工具链已就绪。"

    Write-Stage -Name "Python" -Message "建立项目隔离环境并安装固定依赖。"
    $venvRoot = Join-Path $RecoveryRoot "venv"
    $venvPython = Join-Path $venvRoot "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        & $basePython -m venv $venvRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Python 隔离环境创建失败。"
        }
    }
    $pythonLock = Join-Path $Root "recovery\python-lock.txt"
    $wheelhouse = Join-Path $CacheRoot "wheelhouse"
    $pipArguments = @(
        "-m", "pip", "install",
        "--disable-pip-version-check",
        "--no-input",
        "--require-hashes",
        "-r", $pythonLock
    )
    if (Test-Path -LiteralPath $wheelhouse -PathType Container) {
        $pipArguments += @("--no-index", "--find-links", $wheelhouse)
    }
    & $venvPython @pipArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python 依赖安装失败。"
    }
    Complete-Stage -Name "python" -Detail "Python 隔离环境和构建依赖已就绪。"

    Write-Stage -Name "Node" -Message "按锁文件安装 Electron 开发与打包依赖。"
    $env:PATH = "$(Split-Path -Parent $nodeTools.node);$env:PATH"
    $env:ELECTRON_CACHE = $ElectronCache
    & $nodeTools.npm ci --prefix (Join-Path $Root "electron") --no-audit --no-fund --offline --cache $NpmCache
    if ($LASTEXITCODE -ne 0) {
        throw "Node.js 依赖安装失败。"
    }
    Complete-Stage -Name "node" -Detail "Electron 固定依赖已就绪。"

    Write-Stage -Name "安全" -Message "扫描公开源码树，不读取或依赖 Git 元数据。"
    $scanArguments = @{
        Root = $Root
        GitleaksPath = $gitleaks
        StrictArchive = $StrictArchive
    }
    if ($SkipGitleaks) {
        $scanArguments["SkipGitleaks"] = $true
    }
    & (Join-Path $Root "scripts\scan_public_tree.ps1") @scanArguments
    if ($LASTEXITCODE -ne 0) {
        throw "安全扫描失败。"
    }
    Complete-Stage -Name "security" -Detail "文件系统秘密与隐私扫描通过。"

    Write-Stage -Name "测试" -Message "运行 Python 测试和 JavaScript 语法检查。"
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $venvPython -m unittest discover -s (Join-Path $Root "tests") -t $Root -v
    if ($LASTEXITCODE -ne 0) {
        throw "Python 测试失败。"
    }
    $javascriptFiles = Get-ChildItem -LiteralPath (Join-Path $Root "electron") -Recurse -File -Filter "*.js" |
        Where-Object { $_.FullName -notlike "*\node_modules\*" }
    foreach ($file in $javascriptFiles) {
        & $nodeTools.node --check $file.FullName
        if ($LASTEXITCODE -ne 0) {
            throw "JavaScript 语法检查失败：$($file.FullName)"
        }
    }
    Complete-Stage -Name "tests" -Detail "自动测试和 JavaScript 语法检查通过。"

    if (-not $SkipBuild) {
        Write-Stage -Name "构建" -Message "执行生产引擎、授权器和客户壳验证构建。"
        & (Join-Path $Root "scripts\build_production_validation.ps1") -PythonExecutable $venvPython -NodeExecutable $nodeTools.node
        if ($LASTEXITCODE -ne 0) {
            throw "生产验证构建失败。"
        }
        Complete-Stage -Name "build" -Detail "生产验证构建通过；未生成正式客户包。"
    } else {
        $StageResults["build"] = [ordered]@{ status = "skipped"; detail = "按参数跳过生产验证构建。" }
    }

    $conclusion = if ($SkipBuild) {
        "已具备继续开发能力；生产交付物构建能力本次未验证。"
    } else {
        "已具备继续开发和生成生产交付物的能力；正式客户包未生成。"
    }
    Write-FinalReport -Succeeded $true -Conclusion $conclusion -Failure ""
    Write-Host ""
    Write-Host $conclusion -ForegroundColor Green
    Write-Host "报告：$ReportText"
    exit 0
} catch {
    $message = $_.Exception.Message
    Write-FinalReport -Succeeded $false -Conclusion "恢复失败，尚不具备继续开发或生产交付能力。" -Failure $message
    Write-Host ""
    Write-Host ("[失败] {0}" -f $message) -ForegroundColor Red
    Write-Host "报告：$ReportText"
    exit 1
}
