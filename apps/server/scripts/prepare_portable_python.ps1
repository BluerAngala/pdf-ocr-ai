# 生成安装包用的便携 Python 运行时（官方 embed + site-packages，非 PyInstaller onedir/onefile）
# 输出: apps/desktop/src-tauri/resources/python-runtime/
param(
    [string]$ProjectRoot = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}

$OutDir = Join-Path $ProjectRoot "apps\desktop\src-tauri\resources\python-runtime"
$Marker = Join-Path $OutDir "python.exe"
$ReqFile = Join-Path $ProjectRoot "apps\server\requirements.txt"
$VenvPython = Join-Path $ProjectRoot ".venv312\Scripts\python.exe"
$EmbedVersion = "3.12.10"
$EmbedZipName = "python-$EmbedVersion-embed-amd64.zip"
$EmbedCache = Join-Path $ProjectRoot "tools\python-embed"
$EmbedZip = Join-Path $EmbedCache $EmbedZipName
$EmbedUrl = "https://www.python.org/ftp/python/$EmbedVersion/$EmbedZipName"

function Ensure-EmbedZip {
    if (-not (Test-Path $EmbedCache)) {
        New-Item -ItemType Directory -Path $EmbedCache -Force | Out-Null
    }
    if (Test-Path $EmbedZip) { return }
    Write-Host "[prepare] Downloading $EmbedUrl ..."
    Invoke-WebRequest -Uri $EmbedUrl -OutFile $EmbedZip -UseBasicParsing
}

function Write-PthFile {
    param([string]$Dir)
    $pth = Get-ChildItem -Path $Dir -Filter "python*._pth" | Select-Object -First 1
    if (-not $pth) { throw "python*._pth not found in $Dir" }
    @(
        "python312.zip",
        ".",
        "Lib\site-packages",
        "import site"
    ) | Set-Content -Path $pth.FullName -Encoding ascii
}

if ((Test-Path $Marker) -and -not $Force) {
    Write-Host "[prepare] python-runtime already exists: $OutDir"
    exit 0
}

if (-not (Test-Path $VenvPython)) {
    throw "Missing venv Python: $VenvPython — run: python -m venv .venv312 && pip install -r apps/server/requirements.txt"
}

Ensure-EmbedZip

if (Test-Path $OutDir) {
    Remove-Item -Recurse -Force $OutDir
}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

Write-Host "[prepare] Extract embed package ..."
Expand-Archive -Path $EmbedZip -DestinationPath $OutDir -Force

$SitePackages = Join-Path $OutDir "Lib\site-packages"
New-Item -ItemType Directory -Path $SitePackages -Force | Out-Null
Write-PthFile -Dir $OutDir

Write-Host "[prepare] pip install --target (this may take a few minutes) ..."
$pipArgs = @(
    "-m", "pip", "install",
    "-r", $ReqFile,
    "--target", $SitePackages,
    "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
    "--upgrade",
    "--no-warn-script-location"
)
& $VenvPython @pipArgs
if ($LASTEXITCODE -ne 0) { throw "pip install failed with exit $LASTEXITCODE" }

# 便携包不打包 pytest
Get-ChildItem $SitePackages -Directory -Filter "pytest*" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "[prepare] Done -> $OutDir"
