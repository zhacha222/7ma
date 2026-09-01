# 7MA v2.0.0 多平台镜像构建 + 推送脚本 (Windows PowerShell)
# 用法：
#   .\build-multiarch.ps1 [镜像名:标签]
#   默认镜像: zhacha222/7ma:v2.0.0
param(
    [string]$Image = "zhacha222/7ma:v2.0.0"
)
$ErrorActionPreference = "Stop"
$Platforms = $env:PLATFORMS
if (-not $Platforms) { $Platforms = "linux/amd64,linux/arm64,linux/arm/v7" }

Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "==> 检查 Docker..."
docker version --format '{{.Server.Version}}' 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "错误: 未安装/未启动 Docker。请先安装 Docker Desktop 并启动。" -ForegroundColor Red; exit 1 }

docker buildx version 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "错误: 需要 Docker Buildx（新版 Docker Desktop 自带）。" -ForegroundColor Red; exit 1 }

Write-Host "==> 启用跨平台模拟 (binfmt)..."
docker run --privileged --rm tonistiigi/binfmt --install all

Write-Host "==> 准备 buildx builder (multiarch)..."
docker buildx inspect multiarch 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    docker buildx create --name multiarch --driver docker-container --platform $Platforms --use
}

Write-Host "==> 构建并推送 $Image  平台: $Platforms"
docker buildx build --platform $Platforms -t $Image --push .

Write-Host "==> 完成: $Image"
