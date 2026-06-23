# Railway 部署手册

## 前置条件

- [ ] 已有 Railway 账号（railway.app，可用 GitHub 登录）
- [ ] 已有 Telegram Bot Token（从 @BotFather 获取）
- [ ] 已有 Telegram Chat ID（见附录 A）
- [ ] 已有 Anthropic API Key（console.anthropic.com）
- [ ] 已有 Garmin 账号（运动/睡眠数据来源）
- [ ] 已有 Renpho 账号（体重数据来源）
- [ ] 本机安装 Railway CLI（见步骤 1）

---

## 步骤 1：安装 Railway CLI

```bash
npm install -g @railway/cli
# 或 macOS Homebrew
brew install railway
```

验证安装：

```bash
railway --version
```

---

## 步骤 2：登录 Railway 并创建项目

```bash
railway login
```

浏览器会打开授权页面，点击 Allow。

```bash
# 在项目根目录执行
cd /Users/zuoyuguo/Projects/health-tracker
railway init
```

提示选择时：
- `Create new project` → 输入项目名，如 `health-tracker`
- 选择 `Empty Project`

---

## 步骤 3：添加 PostgreSQL 数据库

```bash
railway add --plugin postgresql
```

Railway 会自动创建 PostgreSQL 实例并注入 `DATABASE_URL` 环境变量，**无需手动填写**。

验证数据库已添加：

```bash
railway variables | grep DATABASE_URL
```

应能看到类似 `DATABASE_URL=postgresql://...` 的输出。

---

## 步骤 4：配置环境变量

逐条执行以下命令（将 `<值>` 替换为真实内容）：

```bash
railway variables set TELEGRAM_BOT_TOKEN=<从BotFather获取的Token>
railway variables set TELEGRAM_CHAT_ID=<你的Chat ID，见附录A>
railway variables set ANTHROPIC_API_KEY=<sk-ant-...>
railway variables set GARMIN_EMAIL=<Garmin账号邮箱>
railway variables set GARMIN_PASSWORD=<Garmin账号密码>
railway variables set GARMINTOKENS=/app/.garmin_tokens
railway variables set RENPHO_EMAIL=<Renpho账号邮箱>
railway variables set RENPHO_PASSWORD=<Renpho账号密码>
railway variables set TIMEZONE=America/Los_Angeles
```

> `DATABASE_URL` 已由步骤 3 自动注入，不需要手动设置。

确认所有变量已设置：

```bash
railway variables
```

应能看到上述 9 个变量（含 `DATABASE_URL` 共 10 个）。

---

## 步骤 5：推送代码并部署

```bash
railway up
```

Railway 会：
1. 上传代码
2. 检测到 `railway.toml`，执行 `alembic upgrade head`（建表）
3. 启动 `python main.py`（Bot + Scheduler）

首次部署约需 2-3 分钟。

---

## 步骤 6：验证部署成功

**查看实时日志：**

```bash
railway logs
```

正常启动日志应包含：

```
INFO  [alembic.runtime.migration] Running upgrade ...
INFO  Application startup complete
INFO  Bot started, polling...
```

**测试 Bot 是否响应：**

在 Telegram 中向你的 Bot 发送：

```
/start
```

Bot 应回复欢迎信息。

```
/status
```

Bot 应回复类似：

```
📊 系统状态
Garmin 睡眠：从未同步
Garmin 运动：从未同步
Renpho 体重：从未同步
```

（首次部署尚未同步，「从未同步」是正确结果）

---

## 步骤 7：等待首次自动同步

定时任务时间（太平洋时间）：

| 任务 | 时间 |
|---|---|
| Garmin + Renpho 同步 | 每天 09:00 |
| 日报推送 | 每天 22:00 |
| 周报推送 | 每周一 08:00 |

首次同步后再发 `/status` 应看到具体时间戳。

**手动触发同步（可选，用于立即验证）：**

```bash
railway run python -c "
from scheduler import garmin_sync_job, renpho_sync_job
garmin_sync_job()
renpho_sync_job()
print('同步完成')
"
```

---

## 步骤 8：上线后第一项验证（P2-4）

首次 Renpho 同步成功后，检查字段映射是否正确：

```bash
railway run python -c "
from renpho_sync.client import RenphoClientWrapper
from renpho_sync.sync import fetch_recent_measurements
import json, os

w = RenphoClientWrapper()
w.connect()
raw = fetch_recent_measurements(w.client)
if raw:
    print(json.dumps(raw[0], indent=2, ensure_ascii=False))
else:
    print('无数据')
"
```

对照输出中的字段名，与 `renpho_sync/sync.py` 的 `parse_measurement` 函数核对：
- `timeStamp` / `bodyfat` / `visfat` / `lbm` / `sinew` 是否存在
- `sinew`（当前映射到 `lean_mass_kg`）是否为肌肉量或去脂体重

若字段名有出入，编辑 `renpho_sync/sync.py` 修正后重新部署（`railway up`）。

---

## 常用运维命令

```bash
# 查看实时日志
railway logs

# 查看所有环境变量
railway variables

# 修改环境变量（修改后服务自动重启）
railway variables set KEY=VALUE

# 手动重启服务
railway restart

# 重新部署（代码有更新时）
railway up

# 进入远程 shell（调试用）
railway shell

# 连接远程数据库（psql）
railway connect postgresql
```

---

## 附录 A：获取 Telegram Chat ID

1. 在 Telegram 搜索 `@userinfobot`，发送 `/start`，它会返回你的 Chat ID（一串数字）。

2. 或者临时启动 Bot 后，向 Bot 发任意消息，然后执行：

```bash
curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
```

在返回 JSON 中找 `message.chat.id` 字段。

---

## 附录 B：Garmin 首次登录说明

`garminconnect` 库首次登录可能需要处理双因素验证（MFA）。如果 Garmin 同步失败并提示 MFA，需要：

1. 在本机先运行一次登录，生成 token 文件
2. 将 token 文件内容通过环境变量 `GARMINTOKENS` 路径写入

目前 `GARMINTOKENS=/app/.garmin_tokens` 指向容器内路径。如 Garmin 有 MFA 要求，Railway 容器每次重启会丢失该文件，需改用数据库或外部存储持久化 token（后续迭代处理）。

---

## 故障排查

| 现象 | 检查点 |
|---|---|
| Bot 不响应 | `railway logs` 看启动报错；确认 `TELEGRAM_BOT_TOKEN` 正确 |
| 数据库错误 | 确认 `DATABASE_URL` 存在；`railway connect postgresql` 验证连接 |
| Garmin 同步失败 | 日志看错误信息；Garmin 账号密码是否正确；是否触发 MFA（见附录 B）|
| Renpho 同步失败 | 日志看错误信息；Renpho 账号密码是否正确 |
| 日报/周报无推送 | 确认 `TELEGRAM_CHAT_ID` 正确；`/status` 确认同步有数据 |
| `alembic upgrade` 报错 | `railway connect postgresql` 进入 psql，`\dt` 查看表是否存在 |
