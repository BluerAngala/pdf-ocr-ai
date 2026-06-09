# onefile 后端 + 冒烟校验 -> Tauri resources/gjj-ocr-server.exe
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$Server = Join-Path $Root "apps\server"
$VenvPy = Join-Path $Root ".venv312\Scripts\python.exe"
$Res = Join-Path $Root "apps\desktop\src-tauri\resources"
$Dst = Join-Path $Res "gjj-ocr-server.exe"

if (-not (Test-Path $VenvPy)) { throw "未找到 $VenvPy" }

# 去掉 onedir 残留，避免安装包混用
$Onedir = Join-Path $Res "gjj-ocr-server"
if (Test-Path $Onedir) {
  try { Remove-Item $Onedir -Recurse -Force -ErrorAction Stop }
  catch { Write-Warning "无法删除旧 onedir（可能正在运行），继续打 onefile: $Onedir" }
}

Write-Host "[bundle] PyInstaller onefile ..."
Push-Location $Server
& $VenvPy -m PyInstaller gjj-ocr-server.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失败" }
Pop-Location

$Src = Join-Path $Server "dist\gjj-ocr-server.exe"
if (-not (Test-Path $Src)) { throw "未生成 $Src" }

& $VenvPy (Join-Path $Server "scripts\verify_server_bundle.py") $Src --resources $Res
if ($LASTEXITCODE -ne 0) { throw "onefile 校验/冒烟失败" }

Copy-Item $Src $Dst -Force
Write-Host "[bundle] -> $Dst"
