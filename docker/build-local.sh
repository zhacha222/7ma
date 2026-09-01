#!/usr/bin/env bash
# 本地快速构建单平台镜像（当前 CPU 架构），用于调试，不推送
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE="${1:-7ma:v2.0.0-local}"
echo "==> 构建本地镜像 $IMAGE"
docker build -t "$IMAGE" .
echo "==> 运行(前台): docker run --rm -p 4321:4321 -v 7ma_config:/app/config -v 7ma_logs:/app/logs $IMAGE"
