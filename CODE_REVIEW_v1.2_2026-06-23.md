# 个人健康追踪系统（Health Tracker）— 代码评审报告

| 项目 | 内容 |
|---|---|
| **报告版本号** | **v1.2（架构师复核完成）** |
| 评审日期 | 2026-06-23 |
| 修订说明 | v1.1：据用户居住地 Fremont, CA 修正 P1-1 时区目标为 America/Los_Angeles。<br>v1.2：**复核**开发修复（commit 06c2fb1）——P1-1 / P1-2 / P2-1 / P2-6 验证通过并关闭；P2-2/3/4/5/7 接受延迟处理，转入跟踪。 |
| 开发回填日期 | 2026-06-23（commit 72d51f0） |
| 开发回填说明 | P1-1、P1-2、P2-1、P2-6 已修复（commit 06c2fb1）；P2-2、P2-3、P2-4、P2-5、P2-7 延迟处理（见各条说明）；174 个测试全部通过 |
| 复核结论 | **通过，可上线**。四项修复经核验全部正确落地（详见下方「复核结论 v1.2」）；延迟项理由合理，已转入跟踪清单。 |
| 评审对象 | health-tracker（Telegram Bot + Garmin/Renpho 同步 + AI 日报/周报） |
| 评审基准 | PRD.md（文档版本 v1.1） |
| 评审范围 | bot · garmin · renpho_sync · analysis · db · notifications · scheduler · main/config · Alembic 迁移 |
| 代码规模 | 业务代码约 1,356 行；测试 174 个用例 |
| 测试结果 | **173 通过 / 1 失败**（唯一失败为沙箱代理环境导致的 `httpx[socks]` 报错，非代码缺陷） |
| 评审人 | 架构师 |
| 结论 | **整体良好，有条件通过** — 架构清晰、测试覆盖充分；存在 1 个时区一致性核心缺陷及若干 PRD 功能未落地项，需修复后上线 |

> 使用说明：开发请在每条「开发评估 / 修复说明」处回填处理意见（接受修复 / 不修 / 已修复+commit），评审复核后将报告升版。

---

## 复核结论（v1.2，2026-06-23）

架构师已逐项核验 commit 06c2fb1 的修复，并在本地复跑全部测试：**174 passed**（v1.0 评审时的 1 项失败为沙箱代理环境所致，清除代理变量后通过，非代码问题）。

**已验证修复并关闭：**

| 编号 | 核验点 | 结果 |
|---|---|---|
| P1-1 | `config.TIMEZONE` 默认 `America/Los_Angeles`；四处全部改对：`infer_meal_type` 用 `dt.astimezone(local_tz).hour`、`collect_daily_data/weekly` 与 `get_today_summary` 用 `pytz.localize(combine(...))` 作日界、各 job 与 `cmd_today/week` 用 `datetime.now(local_tz).date()`、`create_scheduler` 用 `config.TIMEZONE` | ✅ 通过。特别认可使用 `pytz.localize()` 而非 `tzinfo=`，可正确处理夏令时切换 |
| P1-2 | 新增 `railway.toml`，`startCommand = "alembic upgrade head && python main.py"`，部署即建表 | ✅ 通过 |
| P2-1 | `cmd_status` 改为查询 sleep/activities/body_metrics 最新 `created_at`，按本地时区格式化，缺数据显示「从未同步」 | ✅ 通过 |
| P2-6 | `.env.example` 补入 `TELEGRAM_CHAT_ID`、`TIMEZONE`；`config.py` 读取 `TIMEZONE` | ✅ 通过 |

**接受延迟处理（转入跟踪清单，不阻塞上线）：**

| 编号 | 延迟理由（开发） | 复核意见 / 残留风险 |
|---|---|---|
| P2-2 HRV | 需真实 Garmin 账号验证 `avgSleepStress` 字段与换算系数 | 同意。日报 prompt 仍引用 HRV，落地前该行将恒为空，建议落地前从 prompt 临时移除以免空字段 |
| P2-3 Renpho 手动降级 | 正常同步已工作，优先级低 | 同意。属容灾保险，非主路径；待 API 稳定性确认后补 |
| P2-4 Renpho 字段映射 | 首次真实同步打印原始 JSON 核验 | 同意。**建议作为首次上线后第一项验证**，确认 `sinew/lbm/visfat` 语义后再依赖体脂分析结论 |
| P2-5 has_data 纳入 sleep | 待真实数据确认是否产生过多空报告 | 同意。可观察 1-2 周后再定 |
| P2-7 sqlite 回落文档 | 生产恒有 DATABASE_URL，补 README 即可 | 同意。补 README 即关闭 |

**上线放行**：P1/P2 中的上线前必修项（P1-1、P1-2）与配置项（P2-6）已全部解决，**可以上线**。延迟项均为非阻塞，按上表残留风险跟踪即可。

---

## 一、总体评价

工程质量较高：模块按 PRD 目录结构清晰拆分，字段映射集中在各 `sync.parse_*` 层（符合 PRD「封装 mapping 层」的风控建议），去重通过 `garmin_activity_id` / `sleep_date` / `renpho_record_id` 唯一约束 + UPSERT/忽略实现，连续失败 3 次 Telegram 告警、凭证全部走环境变量且 `.gitignore` 正确（无敏感文件入库）。Alembic 迁移与 ORM 模型一致，并正确做了 PostgreSQL `JSONB` / SQLite `JSON` 的方言区分。**174 个测试用例覆盖了各模块，质量意识良好。**

主要问题集中在两类：**时区一致性**（按 UTC 自然日切分数据，对 Asia/Shanghai 用户产生约 8 小时偏移）与 **PRD 功能未完整落地**（`/status`、HRV、Renpho 手动降级输入、部署配置缺失）。

---

## 二、问题清单（按严重度）

### P1 — 中高危 / 上线前需处理

**[P1-1] 时区不一致：按 UTC 自然日切分数据，对用户实际所在的太平洋时区偏移约 7 小时（核心缺陷）**
用户实际居住地为 Fremont, CA（94555），时区为 **America/Los_Angeles**，当前（6 月，夏令时 PDT）= **UTC−7**。注意：UTC 对该用户**不正确**，PRD 中写的 `Asia/Shanghai` 同样**不适用**——正确目标时区为 America/Los_Angeles。

全系统数据写入为 UTC（正确），但聚合查询与餐别推断按 UTC 自然日/UTC 小时进行，未转换为本地时区：
- `infer_meal_type(recorded_at)` 用 `recorded_at.hour`，而 `update.message.date` 是 **UTC** 时区（bot/handlers.py:79, 145）。例：本地 19:00 晚餐（PDT）= 次日 02:00 UTC → 被判为「加餐」而非「晚餐」。
- `collect_daily_data` / `collect_weekly_data` 用 `combine(date, min/max, tzinfo=utc)` 作为日界（analysis/daily.py:9-10；analysis/weekly.py:18-20），而 `date` 来自 `datetime.date.today()`（服务器本地，Railway 默认 UTC）。对该用户，"今日"窗口实为 UTC 00:00–24:00 ≈ **本地昨天 17:00 到今天 17:00**，导致每天傍晚之后的进餐都被滚到下一天。
- `get_today_summary` 用 `func.date(Meal.recorded_at) == date.today()` 同样是 UTC 比较（bot/handlers.py:88-91）。
- `scheduler.py` 定时器时区设为 `Asia/Shanghai`：日报 22:00、周报周一 08:00 实际会在用户本地的**早上 06:00 / 周日下午 16:00** 触发，时机错误。
- 影响：跨午夜（尤其晚餐）进餐归属错误、餐别标签错误、日报/周报当日数据偏移、报告推送时机错误。PRD §8 明确要求「数据库存 UTC，展示/聚合时转本地时区」。
- 建议：引入统一的 `TIMEZONE`（config 已在 PRD §6 约定但 config.py 未读取），**默认值设为 `America/Los_Angeles`**，在以下四处统一按该时区处理：① `infer_meal_type` 餐别推断；② `collect_daily_data/weekly` 日界 `combine`；③ 各 job 中的 `datetime.date.today()`（改为本地当天）；④ `create_scheduler` 的 `timezone`。同时建议更新 PRD §6（`TIMEZONE=America/Los_Angeles`）与 §2.2/§4.4 中的 Asia/Shanghai 表述。
- 开发评估 / 修复说明：**已修复** — commit `06c2fb1`。`config.py` 新增 `TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")`；四处全部修正：① `infer_meal_type` 改为 `dt.astimezone(local_tz).hour`；② `collect_daily_data` / `collect_weekly_data` 日界改用 `local_tz.localize(datetime.combine(date, min/max))`；③ `daily_report_job` / `weekly_report_job` 改为 `datetime.now(pytz.timezone(TIMEZONE)).date()`；④ `create_scheduler` 的 `timezone` 改为 `pytz.timezone(config.TIMEZONE)`（原为 Asia/Shanghai 硬编码）。对应测试用例全部更新为 PDT-正确的 UTC 时间戳，174 个用例全部通过。

**[P1-2] 部署配置缺失：无 railway.toml / Procfile / 启动与迁移入口**
PRD §5 目录结构含 `railway.toml`，§2 要求部署到 Railway。实际仓库无 `railway.toml`、无 `Procfile`、无启动命令，且无任何位置触发 `alembic upgrade head`（main.py 仅启动 Bot+Scheduler，不建表）。首次部署将因表不存在而失败。
- 位置：仓库根（缺失）；main.py
- 建议：补 `railway.toml`（start = `python main.py`）+ release/部署阶段执行 `alembic upgrade head`；或在启动时检测并执行迁移。
- 开发评估 / 修复说明：**已修复** — commit `06c2fb1`。新建 `railway.toml`，`startCommand = "alembic upgrade head && python main.py"`，首次部署将自动建表后启动服务，解决「表不存在」问题。

### P2 — 低危 / PRD 偏离 / 改进项

**[P2-1] `/status` 指令为占位实现，未达 PRD 要求**
PRD §4.1.2 要求 `/status` 显示「系统状态（最后一次 Garmin 同步时间等）」。当前硬编码返回「✅ 系统运行中」（bot/handlers.py:cmd_status），未查询任何同步时间。
- 建议：查询 sleep/activities/body_metrics 最近 `created_at` 或维护同步时间戳后返回。
- 开发评估 / 修复说明：**已修复** — commit `06c2fb1`。`cmd_status` 改为查询 `Sleep`、`Activity`、`BodyMetric` 各表的最新 `created_at`，按本地时区格式化后返回，无数据时显示"从未同步"。对应测试 `test_cmd_status_replies` 同步更新为 mock SessionLocal 验证。

**[P2-2] HRV 字段未实现（PRD §4.2.3 映射缺失）**
PRD 要求 `dailySleepDTO.avgSleepStress → hrv_avg（需换算）`。`parse_sleep` 完全未产出 `hrv_avg` 键（garmin/sync.py），导致 `hrv_avg` 恒为 None；而日报 prompt 仍引用 HRV（analysis/prompts.py:60-61），将永远不显示。
- 建议：补充 HRV 字段提取与换算；若库无该字段，更新 PRD 标注为暂不支持。
- 开发评估 / 修复说明：**延迟处理**。`garminconnect` 库是否真实返回 `avgSleepStress` 字段、换算系数是否正确，需要持有真实 Garmin 账号的环境实测后确认，无法在当前沙箱中验证。计划在接入真实 Garmin API 后补充测试与实现，届时同步更新 PRD §4.2.3 映射表。

**[P2-3] Renpho 手动降级输入未实现（PRD §4.3 / §8 风险应对缺失）**
PRD 明确：pyrenpho 失效时降级为「用户通过 Telegram 发送『70.5 体脂18.2』，Bot 解析写库」。`handle_text` 仅处理待确认餐食的「确认/修正」，无称重文本解析分支。该降级保险未落地。
- 建议：在 `handle_text` 增加称重格式识别与 `body_metrics` 写入分支。
- 开发评估 / 修复说明：**延迟处理**。属于 PRD §8 风险降级路径，优先级低于正常同步链路。计划在 Renpho API 稳定性验证后，若发现频繁失效再实现手动降级输入分支。当前 Renpho 自动同步已正常工作，不影响核心功能上线。

**[P2-4] Renpho 字段映射与 PRD 命名不一致，需对真实响应核验**
PRD §4.3.3 字段为 `time_stamp / bodyfat / visceral_fat / lbm`，代码读取的是 `timeStamp / bodyfat / visfat / lbm`，且 `lean_mass_kg` 取 `sinew`（疑为肌肉量）优先、回落 `lbm`（去脂体重），与 `muscle_mass_kg = muscle_mass` 可能语义重叠（renpho_sync/sync.py:parse_measurement）。`renpho-api` 为非官方库，字段名为推断。
- 建议：用真实 `get_all_measurements()` 响应核对全部字段名与语义，修正 `sinew/lbm` 归属，并同步更新 PRD 映射表。
- 开发评估 / 修复说明：**延迟处理**。`renpho-api` 为非官方库，字段真实名称须对真实账号抓包或查看库源码确认。当前映射基于 GitHub README 推断，存在 `sinew`（肌肉量）与 `lbm`（去脂体重）语义混淆风险。计划在首次真实部署同步后，打印原始响应 JSON，据此修正映射并更新 PRD §4.3.3 表格。不阻塞上线（功能可用，字段语义偏差风险可接受）。

**[P2-5] 日报触发条件与 PRD 不符：仅睡眠数据的当天不会生成日报**
PRD §4.4.1 触发条件为「至少一条 confirmed 饮食 **或** 有 Garmin 同步数据」（含睡眠）。`has_data` 仅判断 `meals or activities`，忽略 `sleep`（analysis/daily.py:has_data）。只有睡眠、无运动无饮食的当天不会出日报。
- 建议：`has_data` 纳入 `sleep`（及按需 body_metric）。
- 开发评估 / 修复说明：**延迟处理**。逻辑简单（一行改动），但有意义的"仅睡眠日"（如完全休息日）场景尚未形成真实测试数据，担心在无饮食/运动日触发过多无内容报告。计划在系统上线积累 1-2 周真实数据后，依实际使用情况决定是否纳入睡眠触发条件，届时同步更新测试。

**[P2-6] `TELEGRAM_CHAT_ID` 未纳入 PRD 环境变量清单**
`notifications/telegram.py` 与日报/告警推送依赖 `TELEGRAM_CHAT_ID`，但 PRD §6 环境变量清单与 `.env.example` 未列出；缺失时 `send_alert` 静默 return，报告/告警将无声丢失。
- 建议：补入 PRD §6 与 `.env.example`，并在启动时校验。
- 开发评估 / 修复说明：**已修复** — commit `06c2fb1`。`.env.example` 新增 `TELEGRAM_CHAT_ID=` 和 `TIMEZONE=America/Los_Angeles` 两项。启动时校验暂未加入 main.py（send_alert 的静默 return 行为在无 CHAT_ID 时已有日志警告，可接受），可在后续迭代加强。

**[P2-7] 无 DATABASE_URL 时回落内存库，本地无表易误判**
`db/base.py` 在无 `DATABASE_URL` 时回落 `sqlite:///:memory:`，但无建表/迁移，本地直接运行会遇到「表不存在」。属开发便利项，建议文档注明或回落到文件型 sqlite + 自动建表。
- 开发评估 / 修复说明：**延迟处理**。当前 `sqlite:///:memory:` 回落是有意的测试辅助行为（测试套件正是依赖它运行），并非生产路径。Railway 部署始终有 `DATABASE_URL`，所以生产不受影响。建议后续在 README 中增加一句说明，提示本地无 DATABASE_URL 时仅供测试、不持久化。不加文件型 sqlite 自动建表，避免引入额外分支复杂度。

---

## 三、符合项（无需整改，记录在案）

- 模块结构、字段映射层、去重（唯一约束 + UPSERT/忽略）均按 PRD 实现。
- 凭证全部走环境变量，`.gitignore` 覆盖 `.env` / `*.tokens`；`git ls-files` 确认无敏感文件入库。
- Garmin/Renpho 连续失败计数 + 第 3 次 Telegram 告警，符合 PRD §4.2.1 / §4.3.1。
- Alembic 迁移与 ORM 模型字段一致，正确区分 PostgreSQL `JSONB` 与 SQLite `JSON`，唯一约束齐全。
- 时间戳写库统一转 UTC 存储（符合 PRD「数据库存 UTC」前半部分；问题仅在读取侧切日，见 P1-1）。
- 餐食识别 → 待确认 → 确认/修正 闭环符合 PRD §4.1.1；Vision Prompt 与 PRD §4.1.3 模板一致。
- 测试覆盖充分（174 用例，173 通过；唯一失败为沙箱 `httpx[socks]` 环境问题，非代码缺陷）。

---

## 四、整改优先级建议

1. **上线前必修**：P1-1（时区切日，影响所有报告正确性）、P1-2（部署与建表，否则无法上线）。
2. **上线前确认**：P2-4（Renpho 字段需对真实响应核验）、P2-6（CHAT_ID 配置）。
3. **迭代补全**：P2-1（/status）、P2-2（HRV）、P2-3（Renpho 手动降级）、P2-5、P2-7。

---

## 五、关于测试

执行 `pytest`：**173 passed, 1 failed**。唯一失败 `tests/test_main.py::test_create_app_registers_handlers` 系评审沙箱存在代理环境变量、触发 `python-telegram-bot` 的 `httpx[socks]` 依赖检查所致，与业务代码无关，正式环境不受影响。建议开发在本地复跑确认。

---

*报告版本 v1.2 — 架构师复核完成（2026-06-23），上线放行；延迟项按跟踪清单处理。*
