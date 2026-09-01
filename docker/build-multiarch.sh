#!/usr/bin/env bash
# 7MA v2.0.0 多平台镜像构建 + 推送脚本（Linux / macOS / WSL）
# 用法：
#   ./build-multiarch.sh [镜像名:标签]
#   默认镜像: zhacha222/7ma:v2.0.0
set -euo pipefail

IMAGE="${1:-zhacha222/7ma:v2.0.0}"
# 需要多平台：linux/amd64, linux/arm64, linux/arm/v7
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64,linux/arm/v7}"

cd "$(dirname "$0")/.."

echo "==> 检查 buildx 与 binfmt"
docker buildx version >/dev/null 2>&1 || { echo "错误: 需要 Docker Buildx（新版 Docker Desktop / Docker Engine 自带）"; exit 1; }

# 启用跨平台模拟（arm 等）
docker run --privileged --rm tonistiigi/binfmt --install all || true

echo "==> 创建 buildx builder（如不存在）"
docker buildx inspect multiarch >/dev/null 2>&1 || docker buildx create --name multiarch --driver docker-container --platform "$PLATFORMS" --use

echo "==> 构建并推送 $IMAGE  平台: $PLATFORMS"
docker buildx build --platform "$PLATFORMS" \
  -t "$IMAGE" \
  --push \
  .

echo "==> 完成: $IMAGE"
