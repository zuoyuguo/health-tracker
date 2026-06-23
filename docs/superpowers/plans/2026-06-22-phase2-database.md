# Phase 2: Database Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 SQLAlchemy 2.0 定义四张核心表的 ORM 模型，用 Alembic 生成并执行迁移脚本，在 Railway PostgreSQL 上创建完整表结构。

**Architecture:** `db/base.py` 持有 SQLAlchemy 引擎和 Session 工厂（从 `DATABASE_URL` 创建），`db/models.py` 定义四张表的 ORM 模型，Alembic 读取 models 自动生成迁移脚本。测试使用 SQLite in-memory 验证模型定义，迁移验证针对真实 PostgreSQL（通过 `DATABASE_URL`）。

**Tech Stack:** Python 3.12, SQLAlchemy==2.0.51, alembic==1.18.4, psycopg2-binary==2.9.12, pytest, SQLite (仅测试用)

## Global Constraints

- SQLAlchemy 2.0 风格（`DeclarativeBase` 子类，不用旧版 `declarative_base()`）
- 所有时间戳字段存 UTC，类型用 `TIMESTAMP(timezone=True)`
- JSONB 字段（meals.foods）用 `sqlalchemy.dialects.postgresql.JSONB`；测试时用 `JSON` fallback
- 数据库凭证从 `DATABASE_URL` 环境变量读取，不得硬编码
- `garmin_activity_id` 和 `renpho_record_id` 必须有 `UNIQUE` 约束
- `sleep_date` 必须有 `UNIQUE` 约束
- Alembic 迁移文件放在 `db/migrations/versions/`
- `alembic.ini` 放在项目根目录

---

## File Map

| 文件 | 职责 |
|------|------|
| `requirements.txt` | 新增 sqlalchemy, alembic, psycopg2-binary |
| `.env.example` | 新增 DATABASE_URL |
| `config.py` | 新增 DATABASE_URL |
| `db/__init__.py` | 空文件，使 db 成为 package |
| `db/base.py` | SQLAlchemy Base 类、engine 工厂、SessionLocal |
| `db/models.py` | 四张表的 ORM 模型：Meal, Sleep, Activity, BodyMetric |
| `alembic.ini` | Alembic 配置（script_location, sqlalchemy.url 占位） |
| `db/migrations/env.py` | Alembic env，导入 models metadata，读取 DATABASE_URL |
| `db/migrations/script.py.mako` | Alembic 迁移模板（alembic init 生成） |
| `db/migrations/versions/001_create_all_tables.py` | 初始迁移：创建四张表 |
| `tests/db/__init__.py` | 空文件 |
| `tests/db/test_models.py` | 用 SQLite in-memory 验证模型可建表、字段完整 |

---

## Task 1: DB 依赖 + config 更新

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `config.py`
- Create: `db/__init__.py`
- Create: `tests/db/__init__.py`

**Interfaces:**
- Produces:
  - `config.DATABASE_URL: str`

- [ ] **Step 1: 更新 requirements.txt**

```text
garminconnect==0.3.6
python-dotenv==1.0.1
pytest==8.3.5
pytest-mock==3.14.0
sqlalchemy==2.0.51
alembic==1.18.4
psycopg2-binary==2.9.12
```

- [ ] **Step 2: 安装新依赖**

```bash
pip3 install -r requirements.txt
```

Expected: 全部安装成功，无报错。

- [ ] **Step 3: 更新 .env.example**

在文件末尾追加：

```env
# Database（Railway 自动注入，本地开发手动填写）
DATABASE_URL=postgresql://user:password@localhost:5432/health_tracker
```

- [ ] **Step 4: 写 config 测试（失败）**

创建 `tests/db/__init__.py`（空文件），创建 `tests/db/test_config_db.py`：

```python
# tests/db/test_config_db.py
def test_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/testdb")
    import importlib, config
    importlib.reload(config)
    assert config.DATABASE_URL == "postgresql://test:test@localhost/testdb"


def test_database_url_default_is_empty(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import importlib, config
    importlib.reload(config)
    assert config.DATABASE_URL == ""
```

- [ ] **Step 5: 运行测试，确认失败**

```bash
pytest tests/db/test_config_db.py -v
```

Expected: `AttributeError: module 'config' has no attribute 'DATABASE_URL'`

- [ ] **Step 6: 更新 config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()

GARMIN_EMAIL = os.getenv("GARMIN_EMAIL", "")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD", "")
GARMIN_TOKEN_PATH = os.getenv("GARMINTOKENS", os.path.expanduser("~/.garmin_tokens"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
```

- [ ] **Step 7: 创建空 package 文件**

创建 `db/__init__.py`（空文件）。

- [ ] **Step 8: 运行测试，确认通过**

```bash
pytest tests/db/test_config_db.py -v
```

Expected: 2 passed.

- [ ] **Step 9: 确认全量测试无回归**

```bash
pytest tests/ -q
```

Expected: 22 passed.

- [ ] **Step 10: Commit**

```bash
git add requirements.txt .env.example config.py db/__init__.py tests/db/__init__.py tests/db/test_config_db.py
git commit -m "feat: add database dependencies and DATABASE_URL config"
```

---

## Task 2: db/base.py — SQLAlchemy Base + 引擎工厂

**Files:**
- Create: `db/base.py`
- Test: `tests/db/test_base.py`

**Interfaces:**
- Consumes: `config.DATABASE_URL: str`
- Produces:
  - `db.base.Base` — SQLAlchemy DeclarativeBase 子类（所有 Model 继承此类）
  - `db.base.get_engine(url: str) -> Engine` — 根据 URL 创建 Engine
  - `db.base.SessionLocal` — `sessionmaker`，绑定到由 `DATABASE_URL` 创建的 engine

- [ ] **Step 1: 写失败测试**

```python
# tests/db/test_base.py
import pytest
from sqlalchemy import text
from db.base import Base, get_engine, SessionLocal


def test_base_is_declarative_base():
    from sqlalchemy.orm import DeclarativeBase
    assert issubclass(Base, DeclarativeBase)


def test_get_engine_creates_engine():
    from sqlalchemy.engine import Engine
    engine = get_engine("sqlite:///:memory:")
    assert isinstance(engine, Engine)
    engine.dispose()


def test_get_engine_connects():
    engine = get_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
    engine.dispose()


def test_session_local_is_callable():
    # SessionLocal 是 sessionmaker 实例，应该可以被调用产生 Session
    session = SessionLocal()
    assert session is not None
    session.close()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/db/test_base.py -v
```

Expected: `ImportError: cannot import name 'Base'`

- [ ] **Step 3: 实现 db/base.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import config


class Base(DeclarativeBase):
    pass


def get_engine(url: str):
    return create_engine(url)


_engine = get_engine(config.DATABASE_URL) if config.DATABASE_URL else get_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=_engine)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/db/test_base.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add db/base.py tests/db/test_base.py
git commit -m "feat: SQLAlchemy base, engine factory, SessionLocal"
```

---

## Task 3: db/models.py — 四张表 ORM 模型

**Files:**
- Create: `db/models.py`
- Test: `tests/db/test_models.py`

**Interfaces:**
- Consumes: `db.base.Base`
- Produces:
  - `db.models.Meal`
  - `db.models.Sleep`
  - `db.models.Activity`
  - `db.models.BodyMetric`

字段完整性要求（与 PRD 严格对应）：

**Meal:** id, recorded_at(TIMESTAMPTZ), meal_type(VARCHAR 20), photo_url(TEXT), foods(JSONB), total_calories(NUMERIC 8,2), protein_g(NUMERIC 6,2), carbs_g(NUMERIC 6,2), fat_g(NUMERIC 6,2), user_note(TEXT), confirmed(BOOLEAN DEFAULT False), created_at(TIMESTAMPTZ DEFAULT now())

**Sleep:** id, sleep_date(DATE UNIQUE), total_sleep_min(INT), deep_sleep_min(INT), light_sleep_min(INT), rem_sleep_min(INT), awake_min(INT), sleep_score(INT), hrv_avg(NUMERIC 6,2), resting_hr(INT), sleep_start(TIMESTAMPTZ), sleep_end(TIMESTAMPTZ), created_at(TIMESTAMPTZ DEFAULT now())

**Activity:** id, activity_date(DATE), activity_type(VARCHAR 50), duration_min(INT), calories_burned(NUMERIC 8,2), avg_hr(INT), max_hr(INT), steps(INT), distance_km(NUMERIC 6,3), hr_zone_1_min~hr_zone_5_min(INT), garmin_activity_id(BIGINT UNIQUE), created_at(TIMESTAMPTZ DEFAULT now())

**BodyMetric:** id, measured_at(TIMESTAMPTZ), weight_kg(NUMERIC 5,2), bmi(NUMERIC 5,2), body_fat_pct(NUMERIC 5,2), fat_mass_kg(NUMERIC 5,2), lean_mass_kg(NUMERIC 5,2), muscle_mass_kg(NUMERIC 5,2), bone_mass_kg(NUMERIC 5,2), water_pct(NUMERIC 5,2), visceral_fat(NUMERIC 5,2), bmr_kcal(INT), renpho_record_id(VARCHAR 64 UNIQUE), created_at(TIMESTAMPTZ DEFAULT now())

- [ ] **Step 1: 写失败测试**

```python
# tests/db/test_models.py
import pytest
from sqlalchemy import inspect, text
from db.base import Base, get_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="module")
def engine():
    """SQLite in-memory engine，用于测试模型定义"""
    e = get_engine("sqlite:///:memory:")
    # 导入 models 触发 mapper 注册
    import db.models
    Base.metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.rollback()
    s.close()


def test_meal_table_exists(engine):
    assert inspect(engine).has_table("meals")


def test_sleep_table_exists(engine):
    assert inspect(engine).has_table("sleep")


def test_activity_table_exists(engine):
    assert inspect(engine).has_table("activities")


def test_body_metric_table_exists(engine):
    assert inspect(engine).has_table("body_metrics")


def test_meal_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("meals")}
    required = {
        "id", "recorded_at", "meal_type", "photo_url", "foods",
        "total_calories", "protein_g", "carbs_g", "fat_g",
        "user_note", "confirmed", "created_at",
    }
    assert required.issubset(cols)


def test_sleep_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("sleep")}
    required = {
        "id", "sleep_date", "total_sleep_min", "deep_sleep_min",
        "light_sleep_min", "rem_sleep_min", "awake_min",
        "sleep_score", "hrv_avg", "resting_hr",
        "sleep_start", "sleep_end", "created_at",
    }
    assert required.issubset(cols)


def test_activity_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("activities")}
    required = {
        "id", "activity_date", "activity_type", "duration_min",
        "calories_burned", "avg_hr", "max_hr", "steps", "distance_km",
        "hr_zone_1_min", "hr_zone_2_min", "hr_zone_3_min",
        "hr_zone_4_min", "hr_zone_5_min",
        "garmin_activity_id", "created_at",
    }
    assert required.issubset(cols)


def test_body_metric_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("body_metrics")}
    required = {
        "id", "measured_at", "weight_kg", "bmi", "body_fat_pct",
        "fat_mass_kg", "lean_mass_kg", "muscle_mass_kg", "bone_mass_kg",
        "water_pct", "visceral_fat", "bmr_kcal",
        "renpho_record_id", "created_at",
    }
    assert required.issubset(cols)


def test_meal_confirmed_defaults_false(session):
    from db.models import Meal
    import datetime
    meal = Meal(
        recorded_at=datetime.datetime.now(datetime.timezone.utc),
        foods=[{"name": "鸡蛋", "weight_g": 60, "calories": 90}],
        total_calories=90,
    )
    session.add(meal)
    session.flush()
    assert meal.confirmed is False


def test_sleep_date_unique_constraint(session):
    from db.models import Sleep
    import datetime
    from sqlalchemy.exc import IntegrityError
    today = datetime.date.today()
    s1 = Sleep(sleep_date=today, total_sleep_min=420)
    s2 = Sleep(sleep_date=today, total_sleep_min=360)
    session.add(s1)
    session.flush()
    session.add(s2)
    with pytest.raises(IntegrityError):
        session.flush()


def test_activity_garmin_id_unique_constraint(session):
    from db.models import Activity
    import datetime
    from sqlalchemy.exc import IntegrityError
    a1 = Activity(activity_date=datetime.date.today(), garmin_activity_id=99999)
    a2 = Activity(activity_date=datetime.date.today(), garmin_activity_id=99999)
    session.add(a1)
    session.flush()
    session.add(a2)
    with pytest.raises(IntegrityError):
        session.flush()


def test_body_metric_renpho_id_unique_constraint(session):
    from db.models import BodyMetric
    import datetime
    from sqlalchemy.exc import IntegrityError
    b1 = BodyMetric(measured_at=datetime.datetime.now(datetime.timezone.utc), renpho_record_id="abc123")
    b2 = BodyMetric(measured_at=datetime.datetime.now(datetime.timezone.utc), renpho_record_id="abc123")
    session.add(b1)
    session.flush()
    session.add(b2)
    with pytest.raises(IntegrityError):
        session.flush()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/db/test_models.py -v
```

Expected: `ImportError: cannot import name 'Meal'` 或类似

- [ ] **Step 3: 实现 db/models.py**

```python
import datetime
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, Integer,
    Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy import DateTime
from sqlalchemy.types import JSON
from db.base import Base

# 用 JSON 代替 JSONB，SQLite 兼容（PostgreSQL 上 Alembic 迁移里单独用 JSONB）
_now = lambda: datetime.datetime.now(datetime.timezone.utc)


class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    meal_type = Column(String(20))
    photo_url = Column(Text)
    foods = Column(JSON, nullable=False, default=list)
    total_calories = Column(Numeric(8, 2))
    protein_g = Column(Numeric(6, 2))
    carbs_g = Column(Numeric(6, 2))
    fat_g = Column(Numeric(6, 2))
    user_note = Column(Text)
    confirmed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)


class Sleep(Base):
    __tablename__ = "sleep"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sleep_date = Column(Date, nullable=False, unique=True)
    total_sleep_min = Column(Integer)
    deep_sleep_min = Column(Integer)
    light_sleep_min = Column(Integer)
    rem_sleep_min = Column(Integer)
    awake_min = Column(Integer)
    sleep_score = Column(Integer)
    hrv_avg = Column(Numeric(6, 2))
    resting_hr = Column(Integer)
    sleep_start = Column(DateTime(timezone=True))
    sleep_end = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_now)


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_date = Column(Date, nullable=False)
    activity_type = Column(String(50))
    duration_min = Column(Integer)
    calories_burned = Column(Numeric(8, 2))
    avg_hr = Column(Integer)
    max_hr = Column(Integer)
    steps = Column(Integer)
    distance_km = Column(Numeric(6, 3))
    hr_zone_1_min = Column(Integer)
    hr_zone_2_min = Column(Integer)
    hr_zone_3_min = Column(Integer)
    hr_zone_4_min = Column(Integer)
    hr_zone_5_min = Column(Integer)
    garmin_activity_id = Column(BigInteger, unique=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class BodyMetric(Base):
    __tablename__ = "body_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    measured_at = Column(DateTime(timezone=True), nullable=False)
    weight_kg = Column(Numeric(5, 2))
    bmi = Column(Numeric(5, 2))
    body_fat_pct = Column(Numeric(5, 2))
    fat_mass_kg = Column(Numeric(5, 2))
    lean_mass_kg = Column(Numeric(5, 2))
    muscle_mass_kg = Column(Numeric(5, 2))
    bone_mass_kg = Column(Numeric(5, 2))
    water_pct = Column(Numeric(5, 2))
    visceral_fat = Column(Numeric(5, 2))
    bmr_kcal = Column(Integer)
    renpho_record_id = Column(String(64), unique=True)
    created_at = Column(DateTime(timezone=True), default=_now)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/db/test_models.py -v
```

Expected: 13 passed.

- [ ] **Step 5: 确认全量测试无回归**

```bash
pytest tests/ -q
```

Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add db/models.py tests/db/test_models.py
git commit -m "feat: SQLAlchemy ORM models for meals, sleep, activities, body_metrics"
```

---

## Task 4: Alembic 初始化 + 迁移脚本

**Files:**
- Create: `alembic.ini`
- Create: `db/migrations/env.py`
- Create: `db/migrations/script.py.mako`
- Create: `db/migrations/versions/001_create_all_tables.py`

**Interfaces:**
- Consumes: `db.base.Base.metadata`（包含所有 model 表定义）
- Produces: Alembic 迁移，可对 PostgreSQL 执行 `alembic upgrade head`

> 此 Task 不写 pytest 测试（Alembic 迁移验证需要真实 DB），但包含对真实 DB 的执行步骤。

- [ ] **Step 1: 初始化 Alembic**

```bash
alembic init db/migrations
```

Expected: 生成 `alembic.ini`（项目根）、`db/migrations/env.py`、`db/migrations/script.py.mako`、`db/migrations/versions/`（空目录）

- [ ] **Step 2: 更新 alembic.ini — 移除硬编码 URL**

打开 `alembic.ini`，找到 `sqlalchemy.url`，改为占位符（实际 URL 在 env.py 里从环境变量读取）：

```ini
sqlalchemy.url = 
```

同时将 `script_location` 确认为：

```ini
script_location = db/migrations
```

- [ ] **Step 3: 更新 db/migrations/env.py**

完整替换 env.py 内容为：

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# 确保项目根目录在 Python path 里
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db.base import Base
import db.models  # noqa: F401 — 触发所有 model 注册到 Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: 生成初始迁移脚本**

```bash
alembic revision --autogenerate -m "create_all_tables"
```

Expected: 在 `db/migrations/versions/` 生成一个类似 `xxxxxxxxxxxx_create_all_tables.py` 的文件。

- [ ] **Step 5: 检查迁移脚本内容**

打开生成的迁移文件，确认：
- `upgrade()` 函数中包含 `op.create_table("meals", ...)` 等四张表
- `meals` 表的 `foods` 列类型为 `JSON`（稍后在 PostgreSQL 上会用 JSONB，见 Step 6）
- 各 UNIQUE 约束存在：`sleep_date`、`garmin_activity_id`、`renpho_record_id`

- [ ] **Step 6: 手动将 meals.foods 改为 JSONB（仅 PostgreSQL）**

在生成的迁移文件里，找到 `foods` 列定义，改为：

```python
from sqlalchemy.dialects.postgresql import JSONB
# ...
sa.Column("foods", JSONB(), nullable=False),
```

（autogenerate 会生成 `JSON`，需手动改为 `JSONB` 以符合 PRD）

- [ ] **Step 7: 在 Railway PostgreSQL 上执行迁移**

确认 `.env` 中 `DATABASE_URL` 已填写 Railway 数据库连接串，然后：

```bash
alembic upgrade head
```

Expected 输出：
```
INFO  [alembic.runtime.migration] Running upgrade  -> xxxxxxxxxxxx, create_all_tables
```

- [ ] **Step 8: 验证四张表已创建**

```bash
python3 -c "
import config
from sqlalchemy import create_engine, inspect
engine = create_engine(config.DATABASE_URL)
tables = inspect(engine).get_table_names()
print('Tables:', tables)
assert 'meals' in tables
assert 'sleep' in tables
assert 'activities' in tables
assert 'body_metrics' in tables
print('All 4 tables exist ✓')
"
```

Expected:
```
Tables: ['activities', 'body_metrics', 'meals', 'sleep']
All 4 tables exist ✓
```

- [ ] **Step 9: Commit**

```bash
git add alembic.ini db/migrations/ 
git commit -m "feat: alembic setup and initial migration for all 4 tables"
```

---

## Self-Review

**Spec coverage 检查：**

| PRD Phase 2 要求 | 计划覆盖情况 |
|----------------|-------------|
| db/models.py — SQLAlchemy 模型 | ✅ Task 3 |
| Alembic 迁移脚本 | ✅ Task 4 |
| meals 表（含 foods JSONB, confirmed DEFAULT False） | ✅ Task 3 + Task 4 Step 6 |
| sleep 表（sleep_date UNIQUE） | ✅ Task 3 (unique=True) |
| activities 表（garmin_activity_id UNIQUE） | ✅ Task 3 (unique=True) |
| body_metrics 表（renpho_record_id UNIQUE） | ✅ Task 3 (unique=True) |
| Railway PostgreSQL 建表完成 | ✅ Task 4 Step 7-8 |
| 凭证从环境变量读取 | ✅ Task 1 config.py + Task 4 env.py |

**Placeholder 扫描：** 无 TBD / TODO / "similar to Task N"。

**Type 一致性：**
- `db.base.Base` 在 Task 2 定义，Task 3 的 models 继承它 ✓
- `Base.metadata` 在 Task 4 env.py 中引用 ✓
- 所有表名与 PRD 一致：`meals`、`sleep`、`activities`、`body_metrics` ✓
