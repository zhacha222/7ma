# 7MA 出行自助服务平台 v2.0.0 —— Docker 部署指南

本文档说明如何把你本机的 7MA 程序打包成 Docker 镜像，并部署到**任意平台**（Windows / Linux / macOS / ARM 盒子 / NAS / 云服务器）。

---

## 一、部署文件说明

| 文件 | 作用 |
| --- | --- |
| `Dockerfile` | 构建镜像：Python 3.10 + Flask，自动启动 web 服务、骑行/积分定时任务、日志清理 |
| `requirements.txt` | 依赖锁定（flask==2.3.3, requests==2.28.1） |
| `.dockerignore` | 排除日志、缓存、桌面版打包产物等，避免打进镜像 |
| `docker-compose.yml` | 一键编排：端口映射 + 数据卷（config / logs）持久化 |
| `docker/build-multiarch.sh` | Linux/macOS 多平台构建并推送 |
| `docker/build-multiarch.ps1` | Windows PowerShell 多平台构建并推送 |
| `docker/build-local.sh` | 本机快速构建单平台镜像（调试用） |

镜像默认监听 **4321** 端口（与程序一致）。

---

## 二、环境准备

安装 Docker（任一平台）：

- **Windows**：安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)（需开启 WSL2）。
- **Linux / 云服务器**：一键脚本或发行版自带方式，见 https://get.docker.com （`curl -fsSL https://get.docker.com | sh`）。
- **macOS Apple Silicon / ARM 盒子**：Docker Desktop 或 Docker Engine 均可。
- 多平台构建需要 **Docker Buildx**（新版 Docker Desktop / Engine 已内置）。

---

## 三、快速开始（Docker Compose）

在 `v2.0.0` 目录：

```bash
# 本地构建并启动（前端端口 4321）
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

启动后访问：**http://localhost:4321**（后台 `/admin`，默认密码 `password`）
> 数据（配置/Authorization/设置）保存在命名卷 `7ma_config`，日志在 `7ma_logs`，重启不丢失。

---

## 四、多平台镜像（生成的可直接用）

`buildx` 可一条命令生成并推送 **linux/amd64、linux/arm64、linux/arm/v7** 三平台镜像（对应 x86 服务器 / 树莓派 ARM64 / 低配 ARM 盒子）。

### 4.1 推送到 Docker Hub（推荐）

```bash
# 登录 Docker Hub（会要求输入账号密码）
docker login

# Linux / macOS
./docker/build-multiarch.sh yourname/7ma:v2.0.0

# Windows PowerShell
.\docker\build-multiarch.ps1 yourname/7ma:v2.0.0
```

镜像名可换成你自己的仓库（如 `zhacha`/`7ma:v1`）。脚本会自动：启用 amd64/arm64/armv7 模拟 → 创建 buildx builder → 构建 → push。

> 推送前需把 `docker-compose.yml` 里的 `image:` 也改成对应的镜像名，这样别的机器可以直接：
> ```bash
> docker compose up -d
> ```

### 4.2 只想在本地构建当前架构（不推送）

```bash
./docker/build-local.sh 7ma:v2.0.0-local
docker rm -f 7ma
docker run -d --name 7ma -p 4321:4321 \
  -v 7ma_config:/app/config -v 7ma_logs:/app/logs \
  7ma:v2.0.0-local
```

---

## 五、手动运行（不用 compose）

```bash
# 构建
docker build -t 7ma:v2.0.0 .

# 运行
docker run -d --name 7ma \
  -p 4321:4321 \
  -v 7ma_config:/app/config \
  -v 7ma_logs:/app/logs \
  --restart unless-stopped \
  7ma:v2.0.0
```

---

## 六、数据与配置

- 所有账号、Authorization、订阅、设置、密码存于 `/app/config`；日志在 `/app/logs`。
- **修改配置**：宿主机映射同名目录即可在外部编辑，或改 compose 为 `./config:/app/config`（便于直接改文件）。
- **忘记密码**：进入容器 `docker exec -it 7ma bash`，执行
  ```bash
  python reset_password.py
  ```
  按提示输入新密码。

---

## 七、常见问题

- **启动后打不开**：确认 `4321` 未被占用，防火墙放行该端口。
- **定时任务不生效**：确认系统时区为 `Asia/Shanghai`（镜像已默认设置），可 `docker exec -it 7ma date` 查看。
- **数据卷丢失**：删容器用 `docker compose down`（不含 `-v`），不会删除数据卷；精简数据用 `docker compose down -v`。
