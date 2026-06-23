# 个人健康追踪系统 · PRD
**Personal Health & Diet Tracker — 产品需求文档 v1.0**

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.1 |
| 创建日期 | 2026-06-22 |
| 负责人 | Zuoyu |
| 状态 | 待开发 |
| 目标读者 | Claude Code / 开发工程师 |

---

## 1. 背景与目标

构建一套个人健康数据闭环系统，整合饮食记录、Garmin 运动健康数据以及 Renpho 体重体脂数据，通过 AI 分析生成有价值的健康洞察，帮助用户理解饮食、睡眠、运动和身体成分之间的相互影响。

**核心目标**
- 降低记录门槛：拍照即可完成饮食记录，无需手动输入
- 自动聚合健康数据：从 Garmin 自动拉取睡眠和运动数据
- 生成有意义的关联分析：发现饮食、睡眠、运动之间的规律
- 定期推送洞察报告：每日总结 + 每周趋势分析，通过邮件送达

**非目标（本期不做）**
- Apple Watch / HealthKit 数据接入
- 多用户支持
- Web Dashboard 可视化界面
- 社交分享功能

---

## 2. 系统架构总览

### 2.1 技术栈

| 模块 | 技术选型 | 说明 |
|------|----------|------|
| 运行环境 | Python 3.11+ | 主语言 |
| 部署平台 | Railway | 与现有 Finance Agent 一致 |
| 数据库 | PostgreSQL (Railway) | 三张核心表 |
| 饮食入口 | Telegram Bot | 用户拍照发送，Bot 触发识别 |
| 图像识别 | Claude API (Vision) | 识别食物种类和估算营养 |
| 营养数据库 | USDA FoodData Central API | 可选，提升营养数据精度 |
| Garmin 数据 | garminconnect Python 库 | 非官方，模拟登录拉取数据 |
| 体重体脂数据 | pyrenpho Python 库 | 非官方，模拟登录 Renpho API 拉取数据 |
| AI 分析 | Claude API | 每晚生成健康洞察文本 |
| 报告推送 | Telegram Bot | 通过 Bot 推送日报 / 周报消息 |
| 定时任务 | Railway Cron / APScheduler | 每天定时拉数据、发报告 |

### 2.2 数据流说明

```
【饮食线】
用户拍照
  → 发送给 Telegram Bot
  → Bot 调用 Claude Vision API 识别
  → 解析食物和营养数据
  → 写入 meals 表
  → Bot 回复识别结果，等待用户确认

【健康线 - Garmin】
Railway Cron 每天 09:00 触发
  → garminconnect 登录拉取前一天数据
  → 解析睡眠数据 → 写入 sleep 表
  → 解析活动数据 → 写入 activities 表

【健康线 - Renpho】
Railway Cron 每天 09:00 触发（与 Garmin 同批）
  → pyrenpho 登录拉取最新称重记录
  → 解析体重、体脂等指标 → 写入 body_metrics 表

【分析线】
每晚 22:00 定时任务启动
  → 查询当日三表数据
  → 组织成 Prompt 调用 Claude API
  → 生成分析文本
  → SendGrid 发送邮件报告
```

---

## 3. 数据库设计

使用 PostgreSQL，通过 Railway 托管，共四张核心表。

### 3.1 meals 表（饮食记录）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | SERIAL PRIMARY KEY | 自增主键 |
| recorded_at | TIMESTAMPTZ NOT NULL | 用户发送照片的时间 |
| meal_type | VARCHAR(20) | 早餐 / 午餐 / 晚餐 / 加餐（由时间推断） |
| photo_url | TEXT | Telegram 图片存储路径（可选） |
| foods | JSONB NOT NULL | 识别到的食物列表，见下方结构 |
| total_calories | NUMERIC(8,2) | 估算总热量 (kcal) |
| protein_g | NUMERIC(6,2) | 蛋白质 (g) |
| carbs_g | NUMERIC(6,2) | 碳水化合物 (g) |
| fat_g | NUMERIC(6,2) | 脂肪 (g) |
| user_note | TEXT | 用户补充备注（可选） |
| confirmed | BOOLEAN DEFAULT FALSE | 用户是否已确认识别结果 |
| created_at | TIMESTAMPTZ DEFAULT NOW() | 记录创建时间 |

`foods` 字段 JSON 结构示例：
```json
[
  {"name": "牛排", "weight_g": 250, "calories": 600},
  {"name": "米饭", "weight_g": 150, "calories": 195},
  {"name": "西兰花", "weight_g": 100, "calories": 35}
]
```

### 3.2 sleep 表（睡眠记录）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | SERIAL PRIMARY KEY | 自增主键 |
| sleep_date | DATE UNIQUE NOT NULL | 对应的睡眠日期（以入睡当天为准） |
| total_sleep_min | INTEGER | 总睡眠时长（分钟） |
| deep_sleep_min | INTEGER | 深睡时长（分钟） |
| light_sleep_min | INTEGER | 浅睡时长（分钟） |
| rem_sleep_min | INTEGER | REM 时长（分钟） |
| awake_min | INTEGER | 清醒时长（分钟） |
| sleep_score | INTEGER | Garmin 睡眠分数（0-100） |
| hrv_avg | NUMERIC(6,2) | 夜间平均 HRV (ms) |
| resting_hr | INTEGER | 静息心率 (bpm) |
| sleep_start | TIMESTAMPTZ | 入睡时间 |
| sleep_end | TIMESTAMPTZ | 起床时间 |
| created_at | TIMESTAMPTZ DEFAULT NOW() | 记录创建时间 |

### 3.3 activities 表（运动记录）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | SERIAL PRIMARY KEY | 自增主键 |
| activity_date | DATE NOT NULL | 活动日期 |
| activity_type | VARCHAR(50) | 运动类型（跑步 / 骑行 / 力量训练等） |
| duration_min | INTEGER | 运动时长（分钟） |
| calories_burned | NUMERIC(8,2) | 消耗热量 (kcal) |
| avg_hr | INTEGER | 平均心率 (bpm) |
| max_hr | INTEGER | 最大心率 (bpm) |
| steps | INTEGER | 步数（仅适用于有氧类） |
| distance_km | NUMERIC(6,3) | 距离（km，适用时） |
| hr_zone_1_min | INTEGER | 心率区间 1 时长（分钟） |
| hr_zone_2_min | INTEGER | 心率区间 2 时长（分钟） |
| hr_zone_3_min | INTEGER | 心率区间 3 时长（分钟） |
| hr_zone_4_min | INTEGER | 心率区间 4 时长（分钟） |
| hr_zone_5_min | INTEGER | 心率区间 5 时长（分钟） |
| garmin_activity_id | BIGINT UNIQUE | Garmin 原始活动 ID，防重复插入 |
| created_at | TIMESTAMPTZ DEFAULT NOW() | 记录创建时间 |

### 3.4 body_metrics 表（体重体脂记录）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | SERIAL PRIMARY KEY | 自增主键 |
| measured_at | TIMESTAMPTZ NOT NULL | 称重时间 |
| weight_kg | NUMERIC(5,2) | 体重 (kg) |
| bmi | NUMERIC(5,2) | BMI |
| body_fat_pct | NUMERIC(5,2) | 体脂率 (%) |
| fat_mass_kg | NUMERIC(5,2) | 脂肪量 (kg) |
| lean_mass_kg | NUMERIC(5,2) | 去脂体重 (kg) |
| muscle_mass_kg | NUMERIC(5,2) | 肌肉量 (kg) |
| bone_mass_kg | NUMERIC(5,2) | 骨量 (kg) |
| water_pct | NUMERIC(5,2) | 体水分率 (%) |
| visceral_fat | NUMERIC(5,2) | 内脏脂肪等级 |
| bmr_kcal | INTEGER | 基础代谢率 (kcal) |
| renpho_record_id | VARCHAR(64) UNIQUE | Renpho 原始记录 ID，防重复插入 |
| created_at | TIMESTAMPTZ DEFAULT NOW() | 记录创建时间 |

> Renpho 秤并非每天都称，`measured_at` 以实际称重时间为准，分析时取最近一条有效记录。

---

## 4. 功能模块详细需求

### 4.1 Telegram Bot — 饮食记录入口

#### 4.1.1 基本交互流程

1. 用户向 Bot 发送一张或多张食物照片
2. Bot 收到图片后立即回复「识别中...」
3. 调用 Claude Vision API，要求返回 JSON 格式的食物清单（含名称、估重、热量、三大营养素）
4. Bot 将识别结果格式化后回复用户：

```
🍽 已识别：
• 牛排 250g — 600 kcal
• 米饭 150g — 195 kcal
• 西兰花 100g — 35 kcal

合计：830 kcal | 蛋白质 52g | 碳水 68g | 脂肪 28g

回复「确认」保存，或直接告诉我需要修正的内容
```

5. 用户回复「确认」→ 写入数据库，`confirmed = true`
6. 用户回复修正内容（如「牛排是 300g」）→ 重新估算后再次请求确认

#### 4.1.2 Bot 指令列表

| 指令 | 功能 |
|------|------|
| /today | 查看今日饮食汇总（热量合计 + 三餐列表） |
| /week | 查看近 7 天热量趋势简报 |
| /note [文字] | 添加文字备注（无照片时快速记录，如「喝了一杯咖啡」） |
| /status | 查看系统状态（最后一次 Garmin 同步时间等） |

#### 4.1.3 Claude Vision API Prompt 模板

```
你是一个专业的营养师助手。请分析这张食物照片，识别所有可见的食物，并以 JSON 格式返回结果。

要求：
- 尽可能准确估算每种食物的重量（克）
- 根据重量估算热量和三大营养素
- 如果无法确定，给出合理的中间估计值
- 只返回 JSON，不要其他文字

返回格式：
{
  "foods": [
    {
      "name": "食物名称（中文）",
      "weight_g": 数字,
      "calories": 数字,
      "protein_g": 数字,
      "carbs_g": 数字,
      "fat_g": 数字
    }
  ],
  "total_calories": 数字,
  "total_protein_g": 数字,
  "total_carbs_g": 数字,
  "total_fat_g": 数字,
  "confidence": "high/medium/low",
  "notes": "识别说明或不确定项（可选）"
}
```

---

### 4.2 Garmin 数据同步模块

#### 4.2.1 认证与 Session 管理

- 使用 `garminconnect` Python 库登录 Garmin Connect
- 将 Session Token 序列化后持久化到本地文件或数据库，避免每次重新登录
- Token 失效时自动重新登录，连续失败 3 次则通过 Telegram 发送告警
- 登录凭证从环境变量读取，不得硬编码

#### 4.2.2 数据拉取策略

- **触发时机**：Railway Cron，每天 09:00（Asia/Shanghai）
- **拉取范围**：前一天的睡眠数据 + 前一天的活动记录
- **防重复**：`activities` 表通过 `garmin_activity_id UNIQUE` 约束防重；`sleep` 表通过 `sleep_date UNIQUE` 防重，重复时执行 UPSERT
- **异常处理**：拉取失败记录错误日志，通过 Telegram 发送通知

#### 4.2.3 Garmin API 字段映射

**睡眠数据：**

| Garmin 返回字段 | 写入字段 | 处理 |
|----------------|---------|------|
| dailySleepDTO.sleepTimeSeconds | total_sleep_min | ÷ 60 |
| dailySleepDTO.deepSleepSeconds | deep_sleep_min | ÷ 60 |
| dailySleepDTO.lightSleepSeconds | light_sleep_min | ÷ 60 |
| dailySleepDTO.remSleepSeconds | rem_sleep_min | ÷ 60 |
| dailySleepDTO.awakeSleepSeconds | awake_min | ÷ 60 |
| dailySleepDTO.sleepScores.overall.value | sleep_score | 直接写入 |
| dailySleepDTO.avgSleepStress | hrv_avg | 需换算，参考库文档 |
| restingHeartRate | resting_hr | 直接写入 |
| dailySleepDTO.sleepStartTimestampGMT | sleep_start | 转换为 UTC TIMESTAMPTZ |
| dailySleepDTO.sleepEndTimestampGMT | sleep_end | 转换为 UTC TIMESTAMPTZ |

**活动数据：**

| Garmin 返回字段 | 写入字段 |
|----------------|---------|
| activityId | garmin_activity_id |
| activityType.typeKey | activity_type |
| duration / 60 | duration_min |
| calories | calories_burned |
| averageHR | avg_hr |
| maxHR | max_hr |
| steps | steps |
| distance / 1000 | distance_km |
| hrTimeInZone[0-4] / 60 | hr_zone_1_min ~ hr_zone_5_min |

---

### 4.3 Renpho 数据同步模块

#### 4.3.1 认证与 Session 管理

- 使用 `pyrenpho` Python 库（或直接调用逆向所得的 Renpho REST API）登录 Renpho 账号
- Session Token 持久化到数据库，避免每次重新登录
- Token 失效时自动重新登录，连续失败 3 次则通过 Telegram 发送告警
- 登录凭证从环境变量读取，不得硬编码

> **注意**：`pyrenpho` 为非官方库，若登录接口失效，备选方案为用户通过 Telegram Bot 手动发送称重数据（如发送「70.5 体脂18.2」），Bot 解析后写入 `body_metrics` 表。

#### 4.3.2 数据拉取策略

- **触发时机**：Railway Cron，每天 09:00（与 Garmin 同批执行）
- **拉取范围**：距上次同步后的所有新称重记录（增量拉取）
- **防重复**：通过 `renpho_record_id UNIQUE` 约束，重复时忽略
- **异常处理**：拉取失败记录错误日志，通过 Telegram 发送通知

#### 4.3.3 Renpho API 字段映射

| Renpho 返回字段 | 写入字段 | 说明 |
|----------------|---------|------|
| time_stamp | measured_at | 转换为 UTC TIMESTAMPTZ |
| id | renpho_record_id | 唯一标识 |
| weight | weight_kg | 体重 |
| bmi | bmi | BMI |
| bodyfat | body_fat_pct | 体脂率 |
| bodyfat_mass | fat_mass_kg | 脂肪量 |
| lbm | lean_mass_kg | 去脂体重 |
| muscle_mass | muscle_mass_kg | 肌肉量 |
| bone_mass | bone_mass_kg | 骨量 |
| water | water_pct | 体水分率 |
| visceral_fat | visceral_fat | 内脏脂肪等级 |
| bmr | bmr_kcal | 基础代谢率 |

---

### 4.4 AI 分析与报告模块

#### 4.4.1 日报（每晚 22:00）

**触发条件**：当日有至少一条 confirmed 饮食记录，或有 Garmin 同步数据

**Prompt 数据输入：**
- 当日所有 meals 记录（含每餐时间、食物、热量、营养素）
- 昨晚的 sleep 记录
- 当日 activities 记录
- 最近一条 body_metrics 记录（若当日有称重则优先使用）

**分析维度：**
- 今日热量摄入 vs 消耗（净差值评估）
- 三大营养素比例评价
- 进餐时间分布（是否有深夜进食）
- 睡眠质量简评（时长、深睡比例、HRV）
- 运动强度评价（若有运动）
- 若当日有称重：体重/体脂简评
- 1-2 条个性化建议

#### 4.4.2 周报（每周一 08:00）

**Prompt 数据输入**：过去 7 天四张表全量数据

**分析维度：**
- 热量摄入趋势（每日数据 + 趋势描述）
- 睡眠质量趋势（平均时长、深睡比例变化）
- 静息心率趋势（是否随运动频率改善）
- 运动频率和总量统计
- 体重 / 体脂变化趋势（若本周有称重记录）
- 关联发现（如：运动日的次日深睡比例更高；热量缺口与体重变化是否一致）
- 本周亮点 + 下周建议

#### 4.4.3 邮件格式规范

- **推送方式**：通过 Telegram Bot 直接发送消息给用户
- **格式**：纯文本 + 少量 Emoji，适配 Telegram 消息排版
- **语言**：中文
- **字数**：日报 300-500 字，周报 500-800 字

---

## 5. 项目目录结构

```
health-tracker/
├── bot/
│   ├── __init__.py
│   ├── handlers.py          # Telegram Bot 消息处理
│   └── vision.py            # Claude Vision API 调用与解析
├── garmin/
│   ├── __init__.py
│   ├── client.py            # garminconnect 封装
│   ├── sync.py              # 数据拉取与写库逻辑
│   └── session.py           # Token 持久化管理
├── renpho/
│   ├── __init__.py
│   ├── client.py            # pyrenpho 封装
│   ├── sync.py              # 体重体脂数据拉取与写库逻辑
│   └── session.py           # Token 持久化管理
├── db/
│   ├── __init__.py
│   ├── models.py            # SQLAlchemy 模型定义（meals/sleep/activities/body_metrics）
│   └── migrations/          # 数据库迁移脚本（Alembic）
├── analysis/
│   ├── __init__.py
│   ├── daily.py             # 日报生成逻辑
│   ├── weekly.py            # 周报生成逻辑
│   └── prompts.py           # Claude Prompt 模板
├── notifications/
│   └── telegram.py          # Telegram 报告推送
├── scheduler.py             # APScheduler 定时任务注册
├── main.py                  # 入口（Bot + Scheduler 启动）
├── config.py                # 环境变量读取
├── requirements.txt
├── railway.toml
└── .env.example
```

---

## 6. 环境变量配置

```env
# Telegram
TELEGRAM_BOT_TOKEN=

# Anthropic
ANTHROPIC_API_KEY=

# Garmin
GARMIN_EMAIL=
GARMIN_PASSWORD=

# Renpho
RENPHO_EMAIL=
RENPHO_PASSWORD=

# Database（Railway 自动注入）
DATABASE_URL=

# 可选
USDA_API_KEY=
TIMEZONE=Asia/Shanghai
```

---

## 7. 开发阶段计划

| 阶段 | 目标 | 交付物 | 优先级 |
|------|------|--------|--------|
| Phase 1 | 验证 Garmin 数据可访问性 | `garmin/client.py` + `garmin/sync.py`，能成功打印昨日睡眠和活动数据 | 🔴 最高 |
| Phase 2 | 数据库搭建 | `db/models.py` + Alembic 迁移脚本，三张表在 Railway PostgreSQL 创建完成 | 🔴 最高 |
| Phase 3 | Telegram Bot 基础版 | `bot/handlers.py` + `bot/vision.py`，能识别食物照片并写入 meals 表 | 🟠 高 |
| Phase 4 | Garmin 自动同步 | `scheduler.py` 集成 Garmin 同步，定时写入 sleep + activities 表 | 🟠 高 |
| Phase 5 | Renpho 数据同步 | `renpho/client.py` + `renpho/sync.py`，验证账号可访问后接入定时任务 | 🟠 高 |
| Phase 6 | AI 分析与报告推送 | `analysis/` + Telegram Bot 推送，能生成并发送日报（含体脂数据） | 🟡 中 |
| Phase 7 | 周报 + 完善 | 周报生成、Bot 查询指令、错误告警 | 🟡 中 |

> **建议从 Phase 1 开始**，快速验证 Garmin 账号的数据可访问性后再投入后续开发。

---

## 8. 关键注意事项与风险

| 风险点 | 说明 | 应对措施 |
|--------|------|----------|
| Garmin 登录风控 | 频繁登录可能被 Garmin 标记为异常 | 持久化 Session Token，避免每次重登 |
| garminconnect 库失效 | Garmin 更新网页端可能导致库失效 | 监控库版本，失效时及时升级 |
| 食物识别误差 | Vision API 估重和热量误差约 20-30% | 用于趋势分析而非精确计量，用户可手动修正 |
| Garmin 字段变更 | 非官方库，字段名可能随 Garmin 更新变化 | 封装 mapping 层，集中管理字段映射 |
| 时区处理 | Garmin 数据使用 GMT，需转换为本地时区 | 统一在写库前转换，数据库存 UTC，展示时再转本地时区 |
| Renpho API 失效 | pyrenpho 为非官方库，接口可能随 App 更新失效 | 失效时降级为 Telegram Bot 手动输入称重数据（发送「70.5 体脂18.2」解析写库） |
| Renpho 称重频率不固定 | 用户不一定每天称重 | 分析时取最近一条有效记录，周报注明本周称重次数 |
