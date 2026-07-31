# Docker Full-Stack and User AI API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the React prototype into a directly testable Docker Compose system backed by MySQL and supporting encrypted user-supplied OpenAI-compatible API configuration.

**Architecture:** Nginx serves the existing React application and proxies `/api` to a FastAPI service. FastAPI owns deterministic analytics, safe query generation, AI provider calls, and persistence through SQLAlchemy/Alembic into MySQL 8.4; a test-only mock LLM proves the external API path without a paid key.

**Tech Stack:** React 19, Vite 7, Nginx, Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PyMySQL, HTTPX, Cryptography/Fernet, MySQL 8.4, Docker Compose, Pytest, Node test runner, Playwright, PowerShell.

## Global Constraints

- Preserve the current six-page information architecture and visual language; do not redesign unrelated UI.
- Use `mysql:8.4` and a named Docker volume; bind published ports to `127.0.0.1` only.
- Seed exactly 540 deterministic sales orders covering 2025-01 through 2026-06, five regions, and six products.
- Never expose a saved API key through frontend responses, browser logs, service logs, query history, or tracked files.
- The AI model returns a validated `QueryIntent`; only backend whitelist mappings may produce executable SQL.
- Executable queries are one parameterized `SELECT`, contain no comments or multiple statements, and enforce a maximum row limit and timeout.
- Local rule mode must support dashboard, query, reports, anomalies, and forecast without any external API.
- AI provider settings support an OpenAI-compatible Base URL, Bearer API key, model name, timeout, enabled state, connection test, update, and delete.
- All repository edits use UTF-8; `.env`, generated keys, logs, database volumes, and build output remain untracked.
- Every behavioral task follows red-green-refactor and ends with a focused commit.

---

## File Structure

### Container and operations

- `compose.yaml`: default MySQL, backend, and frontend services plus the `test` profile mock LLM.
- `.env.example`: non-secret variable names and safe local defaults.
- `.dockerignore`: excludes Git metadata, local dependencies, secrets, build output, and QA artifacts.
- `docker/frontend.Dockerfile`: multi-stage Vite build and Nginx runtime.
- `docker/nginx.conf`: SPA fallback, `/api` proxy, and Nginx health endpoint.
- `scripts/start.ps1`: Docker preflight, secret generation, build, startup, health wait, and URL output.
- `scripts/stop.ps1`: stop services while preserving data.
- `scripts/reset.ps1`: explicit-confirmation data reset.
- `scripts/test.ps1`: unit, integration, frontend, build, and E2E orchestration.

### Backend

- `backend/Dockerfile`: Python 3.12 runtime with app and test dependencies.
- `backend/entrypoint.sh`: migrate, seed, and then start Uvicorn.
- `backend/requirements.txt`: pinned runtime packages.
- `backend/requirements-dev.txt`: pinned test packages.
- `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial.py`: schema migration.
- `backend/app/main.py`: FastAPI construction, middleware, router registration, and exception handlers.
- `backend/app/core/config.py`: environment settings.
- `backend/app/core/errors.py`: typed application errors and response mapping.
- `backend/app/core/crypto.py`: Fernet encryption and key masking.
- `backend/app/db/session.py`: engine and session factory.
- `backend/app/db/models.py`: sales, metric, report, AI provider, and query history ORM models.
- `backend/app/db/seed.py`: deterministic and idempotent seed generation.
- `backend/app/query/schemas.py`: `QueryIntent`, `BuiltQuery`, and query response models.
- `backend/app/query/local_parser.py`: local Chinese query intent resolver.
- `backend/app/query/sql_builder.py`: whitelist-only parameterized SQL generation.
- `backend/app/query/service.py`: resolver selection, execution, summaries, and history.
- `backend/app/analytics/service.py`: dashboard, anomaly, and forecast calculations.
- `backend/app/reports/service.py`: deterministic report generation and optional AI narrative.
- `backend/app/ai/client.py`: OpenAI-compatible HTTP client.
- `backend/app/ai/service.py`: encrypted provider persistence, connection test, intent, and narrative calls.
- `backend/app/api/*.py`: health, metadata, dashboard, query, analytics, reports, settings, and history routes.
- `backend/mock_llm/main.py`: test-only OpenAI-compatible service.
- `backend/tests/unit/*.py`: pure logic and route contract tests.
- `backend/tests/integration/*.py`: real MySQL persistence and API tests.

### Frontend

- `src/lib/apiClient.js`: injectable fetch client and normalized API errors.
- `src/lib/downloads.js`: browser text download helper.
- `src/hooks/useAsync.js`: cancellation-safe async resource state.
- `src/components/AppShell.jsx`: navigation, title bar, and system status.
- `src/components/AsyncPanel.jsx`: stable loading and error presentation.
- `src/views/QueryView.jsx`: remote natural-language query workflow.
- `src/views/DashboardView.jsx`: remote KPI and filter workflow.
- `src/views/ReportView.jsx`: remote report generation and export.
- `src/views/AnomalyView.jsx`: remote anomaly data.
- `src/views/ForecastView.jsx`: remote forecast data.
- `src/views/ConfigView.jsx`: metric metadata, health, and AI provider form.
- `src/App.jsx`: page selection and top-level query handoff only.
- `tests/apiClient.test.mjs`: API client contract tests.
- `tests/e2e/system.spec.js`: full browser acceptance flow.

## Cross-Task API Contract

| Method and path | Owner task | `data` payload |
| --- | --- | --- |
| `GET /api/health` | Task 1/2 | component status, seed count, AI mode |
| `GET /api/metadata` | Task 3 | metrics and distinct filter values |
| `GET /api/dashboard` | Task 3 | KPIs, deltas, trend, regions, products, filters |
| `GET /api/anomalies` | Task 3 | threshold and evidence-backed anomaly items |
| `GET /api/forecast` | Task 3 | monthly history and one estimated next-month point |
| `POST /api/query` | Task 4/6 | engine, intent, SQL, safety, rows, chart, summary |
| `POST /api/reports/generate` | Task 5/6 | title, period, sections, Markdown, engine, timestamp |
| `GET /api/query-history` | Task 5 | newest-first masked query records |
| `GET /api/settings/ai` | Task 6 | configured state and masked provider metadata |
| `PUT /api/settings/ai` | Task 6 | saved masked provider metadata |
| `DELETE /api/settings/ai` | Task 6 | `configured: false` and `ai_mode: local` |
| `POST /api/settings/ai/test` | Task 6 | connection status, provider, model, and latency |

---

### Task 1: Docker foundation and backend health

**Files:**
- Create: `.env.example`
- Create: `.dockerignore`
- Create: `compose.yaml`
- Create: `docker/frontend.Dockerfile`
- Create: `docker/nginx.conf`
- Create: `backend/Dockerfile`
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/errors.py`
- Create: `backend/app/core/logging.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/api/health.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/unit/test_health.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: environment variables from `.env` and Compose service DNS name `mysql`.
- Produces: `create_app() -> FastAPI`, `AppError`, `configure_logging()`, `GET /api/health`, `get_session() -> Iterator[Session]`, and healthy `frontend`, `backend`, and `mysql` containers.

- [ ] **Step 1: Verify or install Docker Desktop**

Run:

```powershell
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  winget install --exact --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
}
```

Start Docker Desktop if installation requests it, then run:

```powershell
docker version
docker compose version
```

Expected: both commands report client and server versions. If WSL 2 enablement requires a restart, restart Windows once and resume this step before changing code.

- [ ] **Step 2: Write the failing health test**

Create `backend/tests/unit/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_app_and_database(monkeypatch):
    monkeypatch.setattr("app.api.health.database_status", lambda: "up")
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "app": "up",
        "database": "up",
        "seeded_orders": 0,
        "ai_mode": "local",
    }
    assert response.json()["request_id"]
```

- [ ] **Step 3: Run the test and verify the missing backend fails**

Run:

```powershell
docker run --rm -v "${PWD}/backend:/app" -w /app python:3.12-slim python -m pytest tests/unit/test_health.py -q
```

Expected: FAIL because FastAPI, Pytest, and `app.main` are not available.

- [ ] **Step 4: Add the minimal backend and container configuration**

Use versions verified from PyPI on 2026-07-10. Create `backend/requirements.txt` with exactly:

```text
fastapi==0.139.0
uvicorn[standard]==0.51.0
pydantic-settings==2.14.2
SQLAlchemy==2.0.51
alembic==1.18.5
PyMySQL[rsa]==1.2.0
httpx==0.28.1
cryptography==49.0.0
```

Create `backend/requirements-dev.txt` with exactly:

```text
pytest==9.1.1
pytest-asyncio==1.4.0
```

Implement `backend/app/core/config.py` with this public model:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str
    app_encryption_key: str
    query_timeout_seconds: int = 5
    ai_default_timeout_seconds: int = 30
    frontend_origin: str = "http://localhost:8080"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Implement `backend/app/api/health.py` so `database_status()` runs `SELECT 1`, `seeded_order_count()` returns zero until the model exists, and `router` returns the test response. Add request ID middleware in `create_app()` using an incoming `X-Request-ID` or `uuid.uuid4().hex` and return it in both the JSON body and response header. Construct FastAPI as `FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url="/api/redoc")` so the approved Nginx URL works without path rewriting.

Define `AppError(code: str, message: str, status_code: int = 400, details: dict | None = None)` and register handlers for `AppError`, request validation failures, and uncaught exceptions. The first two return the approved error envelope; uncaught exceptions log the stack server-side and return code `INTERNAL_ERROR` with no stack in the response. Add CORS middleware allowing only `get_settings().frontend_origin`. Request logging records request ID, method, path, status, and elapsed milliseconds; it must not log headers or bodies.

Compose must use these service contracts:

```yaml
services:
  mysql:
    image: mysql:8.4
    environment:
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
    ports:
      - "127.0.0.1:3307:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -h localhost -uroot -p$$MYSQL_ROOT_PASSWORD --silent"]
      interval: 5s
      timeout: 5s
      retries: 30
  backend:
    build:
      context: ./backend
    env_file: .env
    depends_on:
      mysql:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 5s
      timeout: 5s
      retries: 30
  frontend:
    build:
      context: .
      dockerfile: docker/frontend.Dockerfile
    ports:
      - "127.0.0.1:8080:80"
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost/healthz >/dev/null || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 30
volumes:
  mysql_data:
```

The Nginx configuration must proxy `/api/` without stripping the prefix and use `try_files $uri /index.html` for the React SPA.

- [ ] **Step 5: Build and run the focused test**

Run:

```powershell
docker compose config
docker compose build backend frontend
docker compose run --rm --no-deps backend pytest tests/unit/test_health.py -q
```

Expected: Compose config is valid and `1 passed`.

- [ ] **Step 6: Commit the container foundation**

```powershell
git add .env.example .dockerignore .gitignore compose.yaml docker backend
git commit -m "feat: add Docker full-stack foundation"
```

---

### Task 2: MySQL schema, migrations, and deterministic seed data

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_initial.py`
- Create: `backend/entrypoint.sh`
- Create: `backend/app/db/models.py`
- Create: `backend/app/db/seed.py`
- Create: `backend/tests/integration/conftest.py`
- Create: `backend/tests/integration/test_database.py`
- Modify: `backend/app/api/health.py`
- Modify: `backend/Dockerfile`
- Modify: `compose.yaml`

**Interfaces:**
- Consumes: `get_settings().database_url` and SQLAlchemy session factory from Task 1.
- Produces: ORM classes `SalesOrder`, `MetricDefinition`, `ReportTemplate`, `AIProviderConfig`, `QueryHistory`; `seed_database(session: Session) -> SeedResult`; Alembic revision `0001_initial`.

- [ ] **Step 1: Write failing migration and seed tests**

Create `backend/tests/integration/test_database.py`:

```python
from sqlalchemy import func, select

from app.db.models import MetricDefinition, SalesOrder
from app.db.seed import seed_database


def test_seed_creates_exactly_540_orders_and_is_idempotent(db_session):
    first = seed_database(db_session)
    second = seed_database(db_session)

    order_count = db_session.scalar(select(func.count()).select_from(SalesOrder))
    metric_count = db_session.scalar(select(func.count()).select_from(MetricDefinition))

    assert first.orders_inserted == 540
    assert second.orders_inserted == 0
    assert order_count == 540
    assert metric_count == 5


def test_seed_covers_required_date_and_dimensions(db_session):
    rows = db_session.scalars(select(SalesOrder)).all()

    assert min(row.order_date for row in rows).isoformat().startswith("2025-01")
    assert max(row.order_date for row in rows).isoformat().startswith("2026-06")
    assert len({row.region for row in rows}) == 5
    assert len({row.product_id for row in rows}) == 6
```

- [ ] **Step 2: Run the integration test and verify RED**

Run:

```powershell
docker compose up -d mysql
docker compose run --rm backend pytest tests/integration/test_database.py -q
```

Expected: FAIL because ORM models, migration, fixture, and seed function are missing.

- [ ] **Step 3: Implement ORM models and migration**

Use SQLAlchemy 2 `Mapped` declarations. Required constraints and indexes:

```python
class SalesOrder(Base):
    __tablename__ = "sales_order"
    __table_args__ = (
        Index("ix_sales_order_date_region", "order_date", "region"),
        Index("ix_sales_order_category_customer", "category", "customer_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_order_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    province: Mapped[str] = mapped_column(String(40), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    customer_type: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

Define the remaining tables with these exact ORM attributes:

```text
MetricDefinition:
  id BigInteger primary key autoincrement
  metric_name String(80) not null
  metric_code String(60) unique not null
  formula Text not null
  description Text not null
  enabled Boolean not null default true

ReportTemplate:
  id BigInteger primary key autoincrement
  template_name String(120) unique not null
  report_type String(30) not null
  sections JSON not null
  created_at DateTime server default now
  updated_at DateTime server default now and update now

AIProviderConfig:
  id BigInteger primary key with the application always using id 1
  provider_name String(80) not null
  base_url String(500) not null
  model String(160) not null
  encrypted_api_key Text not null
  api_key_hint String(40) not null
  enabled Boolean not null default true
  timeout_seconds Integer not null default 30
  created_at DateTime server default now
  updated_at DateTime server default now and update now

QueryHistory:
  id BigInteger primary key autoincrement
  question Text not null
  engine String(20) not null
  intent_json JSON nullable
  generated_sql Text nullable
  parameters_json JSON nullable
  summary Text nullable
  status String(20) not null
  error_code String(80) nullable
  duration_ms Integer not null
  created_at DateTime server default now and indexed
```

The migration creates every table, unique constraint, and index and has a complete downgrade in reverse dependency order.

Create `backend/entrypoint.sh` with this startup order:

```sh
#!/bin/sh
set -eu
alembic upgrade head
python -m app.db.seed
exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

Copy it into the backend image, normalize LF line endings, make it executable, and set it as the default entrypoint. The `backend` Compose service uses this default; one-off test commands continue to override the image command.

- [ ] **Step 4: Implement the deterministic idempotent seed**

Expose this result type:

```python
@dataclass(frozen=True)
class SeedResult:
    orders_inserted: int
    metrics_inserted: int
    templates_inserted: int
```

Generate 18 month starts from 2025-01 through 2026-06. Use these region multipliers: 华东/上海 `1.18`, 华南/广东 `0.96`, 华北/北京 `1.05`, 西南/四川 `0.88`, 华中/湖北 `0.92`. Use these product tuples `(id, name, category, unit_price, margin, customer_type)`:

```python
PRODUCTS = (
    (1, "星云 Pro 智能终端", "智能硬件", Decimal("4900"), Decimal("0.25"), "企业客户"),
    (2, "极光 Mini 传感器", "工业传感", Decimal("1500"), Decimal("0.22"), "渠道客户"),
    (3, "云枢 BI 套件", "软件订阅", Decimal("9000"), Decimal("0.45"), "企业客户"),
    (4, "蓝鲸 Edge 网关", "边缘计算", Decimal("4900"), Decimal("0.23"), "政府客户"),
    (5, "辰星 数据服务包", "数据服务", Decimal("8000"), Decimal("0.36"), "企业客户"),
    (6, "光栅智能工作站", "智能硬件", Decimal("3200"), Decimal("0.28"), "渠道客户"),
)
```

For each month, region, and product, create one order with external ID `SEED-{YYYYMM}-{region_index}-{product_id}` and:

```python
quantity = 20 + (((month_index + 1) * 7 + region_index * 11 + product_id * 13) % 181)
season_factor = Decimal("1.00") + Decimal((month_index % 6) - 2) / Decimal("100")
amount = (Decimal(quantity) * unit_price * region_multiplier * season_factor).quantize(Decimal("0.01"))
profit = (amount * margin).quantize(Decimal("0.01"))
order_date = month_start + timedelta(days=(region_index * 5 + product_id * 3) % 27)
```

Insert only external IDs absent from the database. Seed five metric definitions and three report templates by unique code/name using the same idempotent rule.

- [ ] **Step 5: Run migration and integration tests**

Run:

```powershell
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m app.db.seed
docker compose run --rm backend pytest tests/integration/test_database.py -q
docker compose run --rm backend python -m app.db.seed
```

Expected: tests pass; both seed commands report a final total of 540 orders, and the second reports zero inserted orders.

- [ ] **Step 6: Commit database persistence**

```powershell
git add backend/alembic.ini backend/alembic backend/entrypoint.sh backend/app/db backend/app/api/health.py backend/tests/integration backend/Dockerfile compose.yaml
git commit -m "feat: add MySQL schema and deterministic seed data"
```

---

### Task 3: Metadata, dashboard, anomalies, and forecast APIs

**Files:**
- Create: `backend/app/analytics/schemas.py`
- Create: `backend/app/analytics/service.py`
- Create: `backend/app/api/metadata.py`
- Create: `backend/app/api/dashboard.py`
- Create: `backend/app/api/analytics.py`
- Create: `backend/tests/integration/test_analytics_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `SalesOrder`, `MetricDefinition`, SQLAlchemy `Session`.
- Produces: `get_dashboard(session, filters)`, `detect_anomalies(session)`, `forecast_next_month(session)`, and routes `/api/metadata`, `/api/dashboard`, `/api/anomalies`, `/api/forecast`.

- [ ] **Step 1: Write failing API contract tests**

```python
def test_dashboard_returns_filterable_mysql_aggregates(api_client):
    response = api_client.get("/api/dashboard", params={"region": "华东"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data["kpis"]) == {"amount", "quantity", "avg_order_value", "profit_rate"}
    assert data["filters"]["region"] == "华东"
    assert data["regions"]
    assert data["products"]
    assert len(data["trend"]) == 18


def test_anomaly_and_forecast_have_explainable_results(api_client):
    anomalies = api_client.get("/api/anomalies").json()["data"]
    forecast = api_client.get("/api/forecast").json()["data"]

    assert anomalies["items"]
    assert all("evidence" in item for item in anomalies["items"])
    assert forecast["history"]
    assert forecast["prediction"]["is_estimate"] is True
    assert forecast["prediction"]["basis"]
```

- [ ] **Step 2: Run tests and verify missing routes fail**

Run: `docker compose run --rm backend pytest tests/integration/test_analytics_api.py -q`

Expected: FAIL with 404 responses.

- [ ] **Step 3: Implement aggregate services**

Implement filters as equality predicates for `region`, `category`, and `customer_type`. KPI formulas are `SUM(amount)`, `SUM(quantity)`, `SUM(amount)/COUNT(id)`, and `SUM(profit)/SUM(amount)`. Trend groups by year and month; regions and products group and sort by amount descending.

Anomaly detection compares the latest complete month with the previous month per region and flags absolute changes of at least 18 percent. Each item includes `metric`, `region`, `current_value`, `previous_value`, `delta`, `level`, `evidence`, and `inference`. Forecast uses ordinary least squares over the 18 monthly totals and returns one next-month point with slope and sample count in `basis`.

- [ ] **Step 4: Register routes and return consistent envelopes**

Each router receives `Session = Depends(get_session)` and returns:

```python
return {
    "data": service_result.model_dump(mode="json"),
    "request_id": request.state.request_id,
}
```

Metadata includes metric definitions and distinct regions, categories, and customer types. Register all three routers in `create_app()`.

- [ ] **Step 5: Run focused and regression tests**

Run:

```powershell
docker compose run --rm backend pytest tests/integration/test_analytics_api.py -q
docker compose run --rm backend pytest tests/unit/test_health.py tests/integration/test_database.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit analytics APIs**

```powershell
git add backend/app/analytics backend/app/api backend/app/main.py backend/tests/integration/test_analytics_api.py
git commit -m "feat: add MySQL-backed analytics APIs"
```

---

### Task 4: Safe natural-language query service

**Files:**
- Create: `backend/app/query/schemas.py`
- Create: `backend/app/query/local_parser.py`
- Create: `backend/app/query/sql_builder.py`
- Create: `backend/app/query/service.py`
- Create: `backend/app/api/query.py`
- Create: `backend/tests/unit/test_local_parser.py`
- Create: `backend/tests/unit/test_sql_builder.py`
- Create: `backend/tests/integration/test_query_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: metric and dimension whitelist, SQLAlchemy session, optional AI intent resolver added in Task 6.
- Produces: `QueryIntent`, `BuiltQuery`, `parse_local(question) -> QueryIntent`, `build_select(intent) -> BuiltQuery`, `run_query(session, question, resolver=None) -> QueryResult`, and `POST /api/query`.

- [ ] **Step 1: Write failing parser and safety tests**

```python
def test_local_parser_understands_top_product_in_east_china():
    intent = parse_local("上月华东区销售额最高的产品是什么？")

    assert intent.metric == "amount"
    assert intent.dimensions == ["product_name"]
    assert intent.filters["region"] == "华东"
    assert intent.time_range == "latest_month"
    assert intent.sort_direction == "desc"
    assert intent.limit == 1


@pytest.mark.parametrize(
    "text",
    [
        "SELECT * FROM sales_order; DROP TABLE sales_order",
        "SELECT * FROM unknown_table",
        "SELECT * FROM sales_order -- ignore rules",
        "UPDATE sales_order SET amount = 0",
    ],
)
def test_sql_validator_rejects_unsafe_text(text):
    with pytest.raises(UnsafeQueryError):
        validate_read_only_sql(text)
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `docker compose run --rm backend pytest tests/unit/test_local_parser.py tests/unit/test_sql_builder.py -q`

Expected: FAIL because query modules do not exist.

- [ ] **Step 3: Implement validated intent and local resolver**

Define strict literals:

```python
MetricCode = Literal["amount", "quantity", "order_count", "avg_order_value", "profit"]
DimensionCode = Literal["region", "province", "product_name", "category", "customer_type", "month", "week"]


class QueryIntent(BaseModel):
    metric: MetricCode
    aggregation: Literal["sum", "count", "average"] = "sum"
    dimensions: list[DimensionCode] = Field(default_factory=list, max_length=2)
    time_range: Literal["all", "latest_month", "previous_month", "last_30_days"] = "latest_month"
    filters: dict[str, str] = Field(default_factory=dict)
    sort_direction: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=20, ge=1, le=100)
    analysis_kind: Literal["ranking", "trend", "comparison", "detail"] = "ranking"
```

The local parser must support all eight existing sample questions using ordered Chinese keyword rules and return a clear `UnrecognizedQuestionError` when no rule matches.

- [ ] **Step 4: Implement whitelist-only SQL generation and execution**

Map each metric and dimension to constant SQL fragments. User values enter only the `params` dictionary. `BuiltQuery` contains `sql`, `params`, and `display_sql`. `validate_read_only_sql()` rejects semicolons before the optional final terminator, comments, forbidden keywords, and identifiers outside the approved table/column set.

`run_query()` resolves the intent, executes `SET SESSION MAX_EXECUTION_TIME = :timeout_ms` using `get_settings().query_timeout_seconds * 1000`, then executes `text(built.sql)` with parameters. It converts Decimals and dates to JSON-safe values, chooses `line` for time dimensions and `bar` otherwise, creates a deterministic Chinese summary, and writes one `QueryHistory` row for success or failure. The generated query always contains `LIMIT :row_limit`, where the validated intent caps `row_limit` at 100.

- [ ] **Step 5: Add and run the API integration test**

```python
def test_query_api_runs_local_intent_against_mysql(api_client):
    response = api_client.post(
        "/api/query",
        json={"question": "上月华东区销售额最高的产品是什么？"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["engine"] == "local"
    assert data["safe"] is True
    assert data["rows"][0]["product_name"]
    assert data["sql"].startswith("SELECT")
    assert data["summary"]
```

Run:

```powershell
docker compose run --rm backend pytest tests/unit/test_local_parser.py tests/unit/test_sql_builder.py -q
docker compose run --rm backend pytest tests/integration/test_query_api.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit safe query support**

```powershell
git add backend/app/query backend/app/api/query.py backend/app/main.py backend/tests
git commit -m "feat: add safe natural-language query service"
```

---

### Task 5: Reports and query history APIs

**Files:**
- Create: `backend/app/reports/schemas.py`
- Create: `backend/app/reports/service.py`
- Create: `backend/app/api/reports.py`
- Create: `backend/app/api/history.py`
- Create: `backend/tests/unit/test_reports.py`
- Create: `backend/tests/integration/test_reports_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: analytics service, `QueryHistory`, optional narrative callback from Task 6.
- Produces: `generate_report(session, request, narrative=None) -> ReportResult`, `POST /api/reports/generate`, and `GET /api/query-history`.

- [ ] **Step 1: Write failing report tests**

```python
def test_report_contains_only_selected_sections(db_session):
    result = generate_report(
        db_session,
        ReportRequest(report_type="月报", modules=["overview", "region", "forecast"]),
    )

    assert [section.id for section in result.sections] == ["overview", "region", "forecast"]
    assert "销售概览" in result.markdown
    assert "区域分析" in result.markdown
    assert "趋势预测" in result.markdown
    assert "异常指标" not in result.markdown
```

- [ ] **Step 2: Run test and verify RED**

Run: `docker compose run --rm backend pytest tests/unit/test_reports.py -q`

Expected: FAIL because report modules are missing.

- [ ] **Step 3: Implement deterministic report generation**

Accept `report_type` as `周报`, `月报`, or `自定义报告`; validate modules against `overview`, `region`, `ranking`, `anomaly`, and `forecast`. Build each section from analytics service results. Return `title`, ISO period, `sections`, `markdown`, `engine`, and `generated_at`. Reject an empty module list with `REPORT_MODULES_REQUIRED`.

- [ ] **Step 4: Add API and history tests**

```python
def test_report_and_history_endpoints(api_client):
    report = api_client.post(
        "/api/reports/generate",
        json={"report_type": "月报", "modules": ["overview", "region"]},
    )
    api_client.post("/api/query", json={"question": "本月各区域销售额排名如何？"})
    history = api_client.get("/api/query-history")

    assert report.status_code == 200
    assert len(report.json()["data"]["sections"]) == 2
    assert history.status_code == 200
    assert history.json()["data"][0]["question"]
    assert "api_key" not in history.text.lower()
```

Run: `docker compose run --rm backend pytest tests/unit/test_reports.py tests/integration/test_reports_api.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit report persistence**

```powershell
git add backend/app/reports backend/app/api/reports.py backend/app/api/history.py backend/app/main.py backend/tests
git commit -m "feat: add report and query history APIs"
```

---

### Task 6: Encrypted OpenAI-compatible provider integration

**Files:**
- Create: `backend/app/core/crypto.py`
- Create: `backend/app/ai/schemas.py`
- Create: `backend/app/ai/client.py`
- Create: `backend/app/ai/service.py`
- Create: `backend/app/api/settings.py`
- Create: `backend/mock_llm/__init__.py`
- Create: `backend/mock_llm/main.py`
- Create: `backend/tests/unit/test_crypto.py`
- Create: `backend/tests/unit/test_ai_client.py`
- Create: `backend/tests/integration/test_ai_settings_api.py`
- Modify: `backend/app/query/service.py`
- Modify: `backend/app/reports/service.py`
- Modify: `backend/app/main.py`
- Modify: `compose.yaml`

**Interfaces:**
- Consumes: `AIProviderConfig`, Fernet master key, HTTPX transport, query and report service extension points.
- Produces: `encrypt_secret`, `decrypt_secret`, `mask_secret`, `OpenAICompatibleClient`, provider CRUD/test endpoints, AI intent resolver, AI report narrative, and test-profile `mock-llm`.

- [ ] **Step 1: Write failing crypto and client tests**

```python
def test_secret_round_trip_and_masking(fernet_key):
    encrypted = encrypt_secret("sk-test-123456789", fernet_key)

    assert encrypted != "sk-test-123456789"
    assert decrypt_secret(encrypted, fernet_key) == "sk-test-123456789"
    assert mask_secret("sk-test-123456789") == "sk-t...6789"


@pytest.mark.asyncio
async def test_client_normalizes_base_url_and_returns_intent():
    transport = httpx.MockTransport(mock_chat_completion)
    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1/",
        api_key="sk-test",
        model="demo-model",
        timeout_seconds=5,
        transport=transport,
    )

    intent = await client.resolve_intent("本月各区域销售额排名如何？")

    assert intent.metric == "amount"
    assert intent.dimensions == ["region"]
```

- [ ] **Step 2: Run tests and verify RED**

Run: `docker compose run --rm backend pytest tests/unit/test_crypto.py tests/unit/test_ai_client.py -q`

Expected: FAIL because crypto and AI modules do not exist.

- [ ] **Step 3: Implement encryption and the OpenAI-compatible client**

Use `cryptography.fernet.Fernet`. Validate Base URL scheme as HTTP or HTTPS and remove the trailing slash. If the URL path is empty or `/`, append `/v1`; if it already has a path such as `/v1`, preserve that path. Call `{normalized_base_url}/chat/completions`. Send Bearer authentication, model, deterministic temperature zero, and a prompt requesting only one JSON object matching `QueryIntent`.

Map HTTP failures to exact error codes: `AI_AUTH_FAILED` for 401/403, `AI_MODEL_NOT_FOUND` for 404, `AI_RATE_LIMITED` for 429, `AI_TIMEOUT` for HTTPX timeout, and `AI_BAD_RESPONSE` for invalid JSON or schema. Never include the key in exception strings.

Reject a response with `Content-Length` over 1,048,576 bytes or an actual body over that size as `AI_BAD_RESPONSE`. Set HTTPX connect, read, write, and pool timeouts from the validated provider timeout, keep TLS verification enabled, and follow at most five redirects.

- [ ] **Step 4: Implement provider persistence and routes**

`PUT /api/settings/ai` accepts `provider_name`, `base_url`, optional `api_key`, `model`, `timeout_seconds`, and `enabled`. A blank key preserves existing ciphertext; a key is required for the first saved configuration. `GET` returns `configured`, provider fields, and `api_key_hint`. `DELETE` removes the record. `POST /test` accepts an unsaved config or uses the saved config and returns provider, model, latency, and `status: connected`.

Update query service to choose AI only when a saved enabled provider exists; response `engine` is `ai` or `local`. Update report service to call `generate_narrative()` for section copy when AI is enabled while retaining data-derived numbers.

- [ ] **Step 5: Add the test-only mock service and integration test**

The mock service must require `Authorization: Bearer test-key`, expose `/v1/chat/completions`, and return an OpenAI-shaped response whose `choices[0].message.content` is valid `QueryIntent` JSON. Add it to Compose with `profiles: ["test"]`, no host port, and command `uvicorn mock_llm.main:app --host 0.0.0.0 --port 8090`.

```python
def test_ai_settings_are_masked_and_drive_query(api_client):
    saved = api_client.put(
        "/api/settings/ai",
        json={
            "provider_name": "Mock LLM",
            "base_url": "http://mock-llm:8090/v1",
            "api_key": "test-key",
            "model": "mock-model",
            "timeout_seconds": 5,
            "enabled": True,
        },
    )
    tested = api_client.post("/api/settings/ai/test", json={})
    queried = api_client.post("/api/query", json={"question": "本月各区域销售额排名如何？"})

    assert saved.status_code == 200
    assert saved.json()["data"]["api_key_hint"] == "test...-key"
    assert "test-key" not in saved.text
    assert tested.json()["data"]["status"] == "connected"
    assert queried.json()["data"]["engine"] == "ai"
```

Run:

```powershell
docker compose --profile test up -d mysql mock-llm
docker compose --profile test run --rm backend pytest tests/unit/test_crypto.py tests/unit/test_ai_client.py tests/integration/test_ai_settings_api.py -q
```

Expected: all tests pass and test output contains no `test-key` outside test source assertions.

- [ ] **Step 6: Commit user AI integration**

```powershell
git add backend/app/core/crypto.py backend/app/ai backend/app/api/settings.py backend/mock_llm backend/tests compose.yaml backend/app/query/service.py backend/app/reports/service.py backend/app/main.py
git commit -m "feat: support encrypted user AI providers"
```

---

### Task 7: Connect all React views to backend APIs

**Files:**
- Create: `src/lib/apiClient.js`
- Create: `src/lib/downloads.js`
- Create: `src/hooks/useAsync.js`
- Create: `src/components/AppShell.jsx`
- Create: `src/components/AsyncPanel.jsx`
- Create: `src/views/QueryView.jsx`
- Create: `src/views/DashboardView.jsx`
- Create: `src/views/ReportView.jsx`
- Create: `src/views/AnomalyView.jsx`
- Create: `src/views/ForecastView.jsx`
- Create: `src/views/ConfigView.jsx`
- Create: `tests/apiClient.test.mjs`
- Modify: `src/App.jsx`
- Modify: `src/styles.css`
- Modify: `vite.config.js`
- Delete: none; retain local analytics files for deterministic frontend unit regression tests until final cleanup review.

**Interfaces:**
- Consumes: all REST contracts from Tasks 3-6.
- Produces: `createApiClient(fetchImpl)`, stable async states, six remote-backed views, and system health visibility.

- [ ] **Step 1: Write the failing API client test**

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { createApiClient } from '../src/lib/apiClient.js';

test('API client unwraps data and preserves request id', async () => {
  const client = createApiClient(async () => new Response(JSON.stringify({
    data: { app: 'up' },
    request_id: 'req-1',
  }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

  const result = await client.health();

  assert.deepEqual(result.data, { app: 'up' });
  assert.equal(result.requestId, 'req-1');
});

test('API client exposes normalized server errors', async () => {
  const client = createApiClient(async () => new Response(JSON.stringify({
    error: { code: 'AI_AUTH_FAILED', message: 'API 密钥无效' },
    request_id: 'req-2',
  }), { status: 401, headers: { 'Content-Type': 'application/json' } }));

  await assert.rejects(client.testAi({}), (error) => {
    assert.equal(error.code, 'AI_AUTH_FAILED');
    assert.equal(error.requestId, 'req-2');
    return true;
  });
});
```

- [ ] **Step 2: Run test and verify RED**

Run: `npm.cmd test`

Expected: FAIL because `src/lib/apiClient.js` does not exist.

- [ ] **Step 3: Implement the injectable API client and async hook**

`createApiClient(fetchImpl = globalThis.fetch)` exposes `health`, `metadata`, `dashboard(filters)`, `query(question)`, `anomalies`, `forecast`, `generateReport(payload)`, `getAi`, `saveAi(payload)`, `testAi(payload)`, `deleteAi`, and `queryHistory`. Central `request()` parses the envelope, throws `ApiError(code, message, requestId, details)`, and never logs payloads.

`useAsync(load, dependencies)` returns `{ data, error, loading, reload }`, uses `AbortController`, and ignores state updates after unmount.

- [ ] **Step 4: Split and migrate the six views**

Move current view markup into focused files while retaining `MetricCard`, `Charts`, `DataTable`, labels, colors, dimensions, and exports. Replace direct `salesRecords` access as follows:

- Query view calls `client.query(question)` and exports returned rows as CSV.
- Dashboard view calls `client.dashboard(filters)` whenever a filter changes.
- Report view calls `client.generateReport({ report_type, modules })` only when the user clicks Generate; export returned Markdown.
- Anomaly and Forecast views use their named endpoints.
- Config view loads health, metadata, and AI settings; API key input is always blank after save; saved state shows only `api_key_hint`; Test, Save, and Delete have separate progress and error states.
- App shell polls health at initial load and on manual refresh, showing `MySQL 正常`, `本地分析`, or the configured provider name.

Use `AsyncPanel` with stable minimum height for loading and errors so content does not shift. Keep the old local modules imported only by existing unit tests, not by runtime views.

- [ ] **Step 5: Configure development proxy and run frontend checks**

Update Vite:

```javascript
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
});
```

Run:

```powershell
npm.cmd test
npm.cmd run build
docker compose up -d --build
Invoke-RestMethod http://localhost:8080/api/health
```

Expected: Node tests pass, Vite build succeeds, and the proxied health request returns `app: up`, `database: up`, and `seeded_orders: 540`.

- [ ] **Step 6: Commit remote-backed UI**

```powershell
git add src tests/apiClient.test.mjs vite.config.js
git commit -m "feat: connect BI workspace to backend APIs"
```

---

### Task 8: Windows lifecycle scripts and operator documentation

**Files:**
- Create: `scripts/start.ps1`
- Create: `scripts/stop.ps1`
- Create: `scripts/reset.ps1`
- Create: `scripts/test.ps1`
- Modify: `README.md`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Docker Compose services and health endpoint.
- Produces: one-command start, stop, guarded reset, full test workflow, and exact Windows instructions.

- [ ] **Step 1: Write script acceptance checks before implementation**

Record and run these commands; the first run must fail because scripts do not exist:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\reset.ps1
```

Expected: file-not-found errors for all three scripts.

- [ ] **Step 2: Implement secure `.env` generation and startup**

`start.ps1` must:

1. Set `$ErrorActionPreference = 'Stop'`.
2. Change to the repository root using `$PSScriptRoot`.
3. Verify `docker` exists and `docker info` succeeds.
4. When `.env` is absent, generate 24 random bytes as lowercase hex for MySQL passwords and 32 random bytes as URL-safe Base64 for Fernet.
5. Write exactly `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `DATABASE_URL`, `APP_ENCRYPTION_KEY`, `FRONTEND_ORIGIN`, `QUERY_TIMEOUT_SECONDS`, and `AI_DEFAULT_TIMEOUT_SECONDS`.
6. Run `docker compose up -d --build`.
7. Poll `http://localhost:8080/api/health` every two seconds for up to 180 seconds.
8. Require `app=up`, `database=up`, and `seeded_orders=540` before success.
9. Print the app and API docs URLs.

Use `[System.Security.Cryptography.RandomNumberGenerator]::GetBytes()`; never use `Get-Random` for secrets.

- [ ] **Step 3: Implement stop, guarded reset, and test scripts**

`stop.ps1` runs `docker compose down` without `--volumes`.

`reset.ps1` accepts `[switch]$ConfirmReset`. Without it, throw `Refusing to delete MySQL data. Re-run with -ConfirmReset.` With it, run `docker compose down --volumes`, then invoke `start.ps1`.

`test.ps1` starts `mysql` and `mock-llm`, runs Alembic, backend Pytest, `npm.cmd test`, and `npm.cmd run build`. It stops test-only containers in a `finally` block but preserves the default MySQL volume. Task 9 extends this script with browser acceptance after the E2E files exist.

- [ ] **Step 4: Update README with exact workflows**

Document prerequisites, Docker Desktop installation through Winget, first startup, URLs, normal stop, guarded reset, test command, local mode, OpenAI-compatible fields, common Docker/WSL errors, and security notes. State that MySQL runs in Docker and is exposed only at `127.0.0.1:3307`.

- [ ] **Step 5: Verify lifecycle behavior**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
Invoke-RestMethod http://localhost:8080/api/health
docker compose ps
git status --short
```

Expected: startup succeeds, health reports 540 rows, all default services are healthy, and `.env` remains untracked.

- [ ] **Step 6: Commit operations tooling**

```powershell
git add scripts README.md .gitignore
git commit -m "docs: add one-command local operations"
```

---

### Task 9: Browser acceptance, full verification, E-drive sync, and GitHub publication

**Files:**
- Create: `playwright.config.js`
- Create: `tests/e2e/system.spec.js`
- Create: `文档/qa/full-stack-dashboard.png`
- Create: `文档/qa/full-stack-ai-settings.png`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `scripts/test.ps1`
- Modify: `文档/PROCESS_2026-07-09.md`

**Interfaces:**
- Consumes: complete app at `http://localhost:8080`, test-profile mock LLM, lifecycle scripts.
- Produces: repeatable browser acceptance evidence, full test command, updated process record, synchronized E-drive clone, and verified GitHub `main`.

- [ ] **Step 1: Add Playwright and write the failing E2E flow**

Install:

```powershell
npm.cmd install --save-dev @playwright/test
```

Configure `baseURL: 'http://localhost:8080'`, `trace: 'retain-on-failure'`, screenshot on failure, desktop Chrome project, and a 1280 by 900 viewport.

Create a single serial acceptance flow that:

1. Opens the dashboard and asserts the MySQL status and non-zero sales KPI.
2. Runs `上月华东区销售额最高的产品是什么？` and asserts SQL, summary, chart, and table.
3. Changes a dashboard region filter and observes a successful `/api/dashboard` response.
4. Generates a two-section monthly report.
5. Opens anomalies and forecast and asserts evidence/basis text.
6. Saves mock provider URL `http://mock-llm:8090/v1`, key `test-key`, and model `mock-model`.
7. Tests the connection, asserts only a masked key appears, and runs an AI-backed query.
8. Deletes the provider and asserts local mode returns.
9. Captures the two named QA screenshots.

- [ ] **Step 2: Run E2E before starting the test profile and verify RED**

Run: `npm.cmd run test:e2e`

Expected: FAIL because the mock provider service is unavailable or the E2E script is not yet wired to the test profile.

- [ ] **Step 3: Wire the test profile and make E2E pass**

Add package scripts:

```json
{
  "test:e2e": "playwright test",
  "test:all": "npm run test && npm run build && npm run test:e2e"
}
```

Update `scripts/test.ps1` to start `docker compose --profile test up -d --build`, wait for health, and call `npm.cmd run test:e2e`. Use installed Chrome channel so no extra browser download is required on this machine.

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

Expected: backend unit/integration tests, frontend tests, Vite build, and Playwright all pass with no skipped tests.

- [ ] **Step 4: Perform persistence and secret audits**

Run:

```powershell
$before = (Invoke-RestMethod http://localhost:8080/api/health).data.seeded_orders
docker compose restart mysql backend
$after = (Invoke-RestMethod http://localhost:8080/api/health).data.seeded_orders
if ($before -ne 540 -or $after -ne 540) { throw "Persistence check failed" }
git grep -n -I -E "test-key|sk-[A-Za-z0-9]{8,}|APP_ENCRYPTION_KEY=[A-Za-z0-9_-]{40,}" -- ':!文档/superpowers/*' ':!backend/tests/*' ':!tests/e2e/*' ':!.env.example'
git status --short
```

Expected: counts remain 540, secret scan returns no production secret, and only intended QA/process/package changes are pending.

- [ ] **Step 5: Update process documentation and commit acceptance evidence**

Append a 2026-07-10 section to `文档/PROCESS_2026-07-09.md` listing Docker services, MySQL rows, AI configuration behavior, commands run, test counts, browser viewports, and remaining production-only limitations.

```powershell
git add package.json package-lock.json playwright.config.js tests/e2e scripts/test.ps1 文档/qa 文档/PROCESS_2026-07-09.md
git commit -m "test: verify full-stack BI workflow"
```

- [ ] **Step 6: Review all changes against the approved design**

Run:

```powershell
git diff 2ee361a..HEAD --check
git log --oneline 2ee361a..HEAD
git status --short --branch
```

Use the `review` skill. Resolve every P0/P1/P2 finding, add a failing regression test before behavioral fixes, rerun the affected tests, then rerun `scripts/test.ps1` once after the final change.

- [ ] **Step 7: Push and synchronize the E-drive checkout**

Run from the C workspace:

```powershell
git push origin main
git ls-remote origin refs/heads/main
```

Then run from `E:\smart-bi-insight-report-platform`:

```powershell
git pull --ff-only
git status --short --branch
git rev-parse HEAD
```

Expected: local C workspace, GitHub `main`, and E-drive checkout report the same commit; both worktrees are clean except ignored runtime files.

---

## Completion Audit

Before reporting completion, collect direct evidence for every approved requirement:

- Docker Desktop command and engine both available.
- Default Compose services healthy.
- MySQL contains exactly 540 seed orders and remains at 540 after restart.
- All six pages fetch backend/MySQL data.
- Local query, report, anomaly, and forecast flows work without API configuration.
- Mock OpenAI-compatible provider saves, masks, tests, drives a query, and deletes successfully.
- Invalid authentication, timeout, bad response, unsafe SQL, and unrecognized question tests pass.
- API key does not appear in settings responses, browser logs, service logs, query history, tracked files, or screenshots.
- Backend unit/integration tests, Node tests, Vite build, and Playwright acceptance all pass with no skips.
- README and process documentation contain the exact verified commands and URLs.
- C workspace, GitHub `main`, and `E:\smart-bi-insight-report-platform` share the same final commit.
