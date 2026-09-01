# 7MA 出行自助服务平台 v2.0.0
# 多平台基础镜像（amd64 / arm64 / armv7 等由 buildx 组合）
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    APP_PORT=4321

# 时区数据，保证日志/定时任务按北京时间
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖，利用构建缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目源码（已由 .dockerignore 排除敏感/临时文件）
COPY . .

# 数据目录（config / logs）挂载为卷，持久化
VOLUME ["/app/config", "/app/logs"]

# 启动时自动启动：web 服务 + 骑行定时任务 + 积分定时任务 + 日志清理
# （app.py 的 __main__ 已经依次 start_scheduler / points_scheduler.main / maintenance.main）
CMD ["python", "app.py"]

EXPOSE 4321
