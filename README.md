# 7MA 出行自助服务平台

基于 Flask 的 **7MA 出行** 自动化服务平台。利用「下单开锁后立即还车、一分钟内免费」的规则实现自动免费用车，并配套完整管理后台：多账号管理、积分获取与自动兑换、认证、订单/日志监控、多渠道消息通知与远程 API。

## ⚠️ 免责申明（Disclaimer）

**请在使用前仔细阅读本声明。使用本项目即表示您已阅读、理解并同意以下全部内容；如不同意，请勿下载、使用或分发本项目。**

本项目仅供**技术学习、学术研究与安全测试**之用，**禁止用于任何商业用途或非法行为**。

- **与平台方关系**：本项目与「7MA」「7mate」等任何平台方或第三方**均无关联，亦未获得任何明确授权**；文中名称仅用于识别相关接口，不构成任何隶属关系或商业合作。
- **使用风险自担**：本项目可能涉及目标平台的服务条款、用户协议及当地法律法规的适用问题。由使用本项目所产生的一切**责任、风险及后果**（包括但不限于账号封禁、押金罚没、资金损失、违约金、法律纠纷等）**均由使用者自行承担**。
- **开发者免责**：开发者对本项目「按现状」提供，**不提供任何形式的担保**，不对因使用本项目造成的任何直接或间接损失**承担任何责任**；并**不承诺不因本项目导致任何第三方损失**。
- **遵守规则**：请务必在**遵守目标平台服务条款与当地法律法规**的前提下使用；合理、审慎、适度地使用，不利用本项目从事任何违法违规或违反平台规则的行为。
- **无恶意代码与隐私**：本项目不包含任何恶意代码、后门或挖矿程序，**不会收集、上传或泄露您的任何凭据与隐私数据**；所有数据仅保存在您自有的运行环境中。
- **停止使用**：如您违反上述任何条款或使用目的超出「技术学习与研究」范畴，请立即停止使用并删除本项目及其所有副本。

---

## 🛡️ 安全与合规建议

- 请在**隔离、非生产**环境中测试，避免影响他人与正常业务。
- 请勿将您的账号凭据、密钥用于任何非授权用途；定期更换密码。
- 本工具的接口实现可能随平台更新而失效，请自行评估风险。

---

## ✨ 功能特性

- **多账号并发用车**：支持导入多个 `Authorization`，自动搜索可用账号下单；所有账号都在骑行中时等待（最多 2 分钟）到有账号还车后自动下单。
- **自动还车监控**：下单开锁后，后台持续监控 60 秒、每 3 秒检测进行中订单，出现立即还车并复核，即使还车成功仍继续监控满一分钟，防止「假性还车」导致超时扣费。
- **管理后台**（`/admin`，默认密码 `password`）：
  - 账号管理：批量导入 / 手动添加 / 手机号登录获取授权、编辑删除排序、账户资产与认证信息、批量自动认证。
  - 积分获取：查看各账号姓名、学校、手机号、注册时间、ID、信用积分、当前积分，支持运行 / 定时运行（可批量）/ 自动兑换骑行卡（188 积分/张）/ 查看日志。
  - 订单信息：按下单时间 / 账号 / 状态 / 车辆编号 / 操作类型 / 详情展示，支持筛选排序、删除记录。
  - 日志查看：日志文件分类展示、弹窗查看内容、删除文件。
  - 设置：日志自动清理天数、API 密钥、通知渠道（多渠道绑定）、修改密码。
  - 教程文档：各通知渠道接入教程。
- **多渠道消息通知**：支持 Telegram、钉钉、企业微信、飞书、Server酱、PushPlus、Bark、QQ 机器人、ntfy、Gotify、自定义 Webhook；单个事件可独立开关（登录后台 / 订单及还车状态 / 积分结果及账号统计 / 添加账号），可「测试消息」。
- **远程 API**：通过 `X-API-Key` 鉴权，提供下单与状态查询接口。

---

## 📁 项目结构

```text
.
├── app.py                 # Flask 主程序：页面、订单流程、后台路由、API
├── auth_store.py          # Authorization 读写（config/authorizations.txt）
├── scheduler.py           # 还车监听调度（每 60 秒，检测订单立即还车）
├── return_logic.py        # 还车监控：持续检查订单并自动还车、防假性还车
├── points.py / points_store.py / points_scheduler.py   # 积分任务、定时、批量兑换
├── certification.py       # 认证（免押金汽车）状态查询与批量认证
├── phone_login.py         # 手机号登录获取 Authorization（滑块验证）
├── device_store.py        # 设备 ID 持久化
├── notify.py              # 多渠道通知发送
├── settings_store.py      # 后台密码、日志清理、API 密钥、通知设置持久化
├── maintenance.py         # 日志定期清理
├── reset_password.py      # 命令行重置后台密码
├── Dockerfile             # 构建镜像（Python 3.10 + Flask）
├── docker-compose.yml     # Docker Compose 一键编排
├── requirements.txt       # Python 依赖锁定
├── docker/                # 多平台构建 / 快速构建脚本与 Docker 部署文档
├── templates/             # 前端页面模板
├── config/                # 配置文件（gitignore）
└── logs/                  # 运行日志（gitignore）
```

---

## ⚙️ 环境要求

- 源码运行：Python 3.7+（推荐 3.9+），依赖 `Flask`、`requests`。
- Docker 部署：任意安装了 Docker 的平台（Docker Desktop / Docker Engine）。

---

## 🚀 部署方式

### 方式一：Windows 部署（推荐：直接使用 Release 里的 exe）

Windows 用户无需安装 Python，直接下载即用：

1. 到 [GitHub Releases](https://github.com/zhacha222/7ma/releases) 下载 `7MA_v2.0.0.exe`（或安卓 `7MA.apk`）。
2. 双击 `7MA_v2.0.0.exe` 运行，服务启动后会自动打开浏览器。
3. 访问 `http://localhost:4321`，后台 `/admin`，**默认密码 `password`**。

> 桌面版已内置本地服务与定时任务，双击即用；数据保存在程序同目录下的 `config/`、`logs/`。

### 方式二：Linux 从源码运行

需要 Python 3.7+（推荐 3.9+）：

```bash
# 1. 克隆或上传源码到服务器
git clone https://github.com/zhacha222/7ma.git  # 或直接上传项目文件

# 2. 安装依赖
cd 项目目录
pip install -r requirements.txt
# 或：pip install Flask requests

# 3. 启动服务
python app.py            # 前台运行
nohup python app.py > server.log 2>&1 &   # 后台运行
```

访问 `http://服务器IP:4321`，后台 `/admin`，**默认密码 `password`**。

> 建议使用 systemd / supervisor 托管进程，保证长期在线，并放行 4321 端口。

### 方式三：自行从源码构建 Docker 镜像

适合想自定义 / 离线构建的场景：

```bash
cd 项目目录

# 只构建本机架构
docker build -t 7ma:v2.0.0 .

# 多平台镜像（amd64 / arm64 / arm/v7），一行生成并推送
docker login
./docker/build-multiarch.sh zhacha222/7ma:v2.0.0     # Linux/macOS
.\docker\build-multiarch.ps1 zhacha222/7ma:v2.0.0    # Windows PowerShell
```

> 离线 / 无网络时，先在有网络机器上 `docker pull python:3.10-slim` 备好，再内网构建。

### 方式四：Docker 一键部署（直接拉取已发布镜像）

只需一台装有 Docker 的机器（任选一种）：

```bash
# docker run 方式
docker run -d --name 7ma -p 4321:4321 \
  -v 7ma_config:/app/config \
  -v 7ma_logs:/app/logs \
  --restart unless-stopped \
  zhacha222/7ma:v2.0.0
```

访问 `http://服务器IP:4321`，后台 `/admin`，**默认密码 `password`**。

### 方式五：Docker Compose 部署（推荐，含数据卷编排）

在任意机器上，把本项目 `docker-compose.yml` 放到一个空目录（`image` 已指向 `zhacha222/7ma:v2.0.0`）：

```bash
docker compose up -d          # 首次自动拉取镜像并启动
docker compose logs -f        # 查看日志
docker compose down           # 停止
```

如未使用本项目自带 compose，可用最小示例：

```yaml
services:
  7ma:
    image: zhacha222/7ma:v2.0.0
    container_name: 7ma
    restart: unless-stopped
    ports:
      - "4321:4321"
    volumes:
      - 7ma_config:/app/config
      - 7ma_logs:/app/logs
    environment:
      - TZ=Asia/Shanghai

volumes:
  7ma_config:
  7ma_logs:
```

---

## 🔑 后台登录 / 修改与重置密码

### 默认密码

- 后台地址：`http://<_主机IP>:4321/admin`
- 默认密码：**`password`**（未修改时生效，登录入口有提示）
- 首次登录后请在「设置 → 修改密码」中更改为强密码。

### 各平台「忘记密码」重置方法

> 无论哪个平台，重置的原理都是运行 `python reset_password.py [新密码]`。下面分平台给出进入该脚本环境的方式。

**① Windows 桌面版（exe）**
- 在 `desktop` 目录（exe 同目录）打开命令行 PowerShell：
  ```powershell
  python reset_password.py 你的新密码
  ```
- 不带参数则交互式输入并二次确认。

**② Linux / 源码运行**
```bash
cd 7ma项目目录
python reset_password.py 你的新密码
```

**③ Docker 容器**
- 进入容器执行：
  ```bash
  docker exec -it 7ma bash
  python reset_password.py 你的新密码
  ```
- 或一条命令：
  ```bash
  docker exec -it 7ma python reset_password.py 你的新密码
  ```

> 无参数执行时会交互式输入：密码至少 4 位。重置后需重新登录后台。

---

## 🖥️ 管理后台

| 侧边栏板块 | 说明 |
| --- | --- |
| 账号管理 | Authorization 列表、资产、手机号登录、批量选择、批量认证等 |
| 订单信息 | 下单/还车/失败等订单记录，筛选 + 排序 + 删除 |
| 积分获取 | 运行 / 定时 / 批量运行 / 批量兑换骑行卡 / 自动积分，查看日志 |
| 日志查看 | 分类日志文件，弹窗查看内容、删除文件 |
| 设置 | 日志清理天数、API 密钥、通知渠道、修改密码 |
| 教程文档 | 各通知渠道接入教程 |

---

## 🔑 远程 API（密钥鉴权）

在「设置 → API 密钥」查看 / 重新生成 `X-API-Key`，调用时在请求头携带，已开启 CORS。

### 查询服务状态

```
GET /api/v1/status
Header: X-API-Key: <你的密钥>
```

```json
{"authorizations": 1, "ok": true, "time": "2026-08-31 12:00:00"}
```

### 远程下单

```
POST /api/v1/order
Header: X-API-Key: <你的密钥>
Body(JSON): {"bike_number": "123456"}
```

```json
{"message": "下单", "unlock_result": "开锁成功", "is_success": true}
```

---

## 🔔 消息通知

「设置 → 通知渠道」支持绑定多个渠道并同时推送：Telegram、钉钉、企业微信、飞书、Server酱、PushPlus、Bark、QQ 机器人、ntfy、Gotify、自定义 Webhook。每个事件可独立开关（单独登录后台 / 请求订单及还车状态 / 积分获取结果及账号统计 / 添加账号），每个绑定可「测试消息」并查看最近一次发送状态。

推送配置详细教程见后台「教程文档」。

---

## 🧩 使用流程（免费用车）

1. 前端填写单车编号并下单。
2. 系统持续在多个账号中搜索可用账号（所有账号有订单时最多等待 2 分钟）。
3. 下单成功后立即开锁并返回结果；后台同时启动「还车监控」。
4. 还车监控持续 1 分钟、每 3 秒检测进行中订单，出现即还车并复核，直到确认无进行中订单，防止超时扣费。

---

## ❓ 常见问题

- **最低 Python 版本？** 源码运行建议 Python 3.7+，推荐 3.9+；Windows 推荐直接使用 exe。
- **Authorization 失效 / 401？** 重新抓包并在「账号管理」中更换或重新登录。
- **一直提示无可用账号？** 所有账号均有未完成行程，等待还车后自动重试；超过 2 分钟仍未成功则提示失败。
- **通知收不到？** 在「设置 → 通知渠道」点击「测试消息」，查看最近一次状态与错误。
- **Docker 无法启动？** `docker logs 7ma` 查看；确认 4321 端口未被占用、时区为 `Asia/Shanghai`。

---

---

## 📄 License（开源协议）

本项目采用 **GNU General Public License v3.0（GPL-3.0）** 开源协议开源，完整条款见 [LICENSE](./LICENSE)。

**署名说明**：本项目由社区开发者共同维护，不指定单一官方作者；基于 GPL-3.0，源码可自由查看、修改与分发。

**GPL-3.0 核心义务（要点）**
- **自由使用**：任何人可免费使用、研究、修改与分发本软件。
- **保持开源**：分发经过修改的版本时，必须同时以 GPL-3.0 协议**完整开源**，并提供对应源代码。
- **传染性**：基于本软件创作的衍生作品（含结合/链接组成部分）须以 GPL-3.0 授权；而与用户的接口调用、业务数据**不构成衍生作品**。
- **无担保**：本软件「按现状」提供，在适用法律允许范围内**不附带任何明示或默示的担保**，开发者不对任何使用后果承担责任。

**第三方依赖**：本项目依赖 `Flask`、`requests` 等开源库，均遵循其各自的开源许可证。

> 商用或二次发布前，请务必完整阅读 [LICENSE](./LICENSE)，必要时咨询法律专业人士，确保符合合规要求。

---

## 📄 附：免责申明速览

本项目仅供技术学习与研究，**禁止商业用途**；与 7MA 等平台无任何关联与授权。使用本项目造成的一切责任与后果（账号封禁、资金损失、法律纠纷等）均由使用者自行承担，开发者「按现状」提供且不承担任何担保与责任。详情见文首「免责申明」。

