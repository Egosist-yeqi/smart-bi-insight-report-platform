# AI Project Context: Smart BI Insight Report Platform

Read this file before modifying the project. It is a concise, implementation-oriented handoff for another AI or developer.

## Project at a glance

- **Purpose:** local, demonstrable intelligent BI platform for Project 11. It turns controlled Chinese business questions into safe data results, charts, analysis summaries, reports, anomaly clues, forecasts, and scenario-based decision prompts.
- **Repository root:** this directory. Local Windows runnable copy is normally `E:\smart-bi-insight-report-platform`.
- **Public entry:** `http://localhost:8080`; API docs: `/api/docs`.
- **Stack:** React 19 + Vite frontend, Nginx reverse proxy, FastAPI backend, SQLAlchemy/Alembic, MySQL 8.4, Docker Compose.
- **Run:** Windows users can double-click `启动智能BI系统.cmd`. Stop with `停止智能BI系统.cmd`.

## Product boundaries

1. The system is a decision-support prototype, not an autonomous decision maker. Anomaly explanations are evidence and checks, not causal proof. Forecasts are indicative only.
2. It supports five demo scenarios: ecommerce, hospital, banking, manufacturing, and internet. Switching a scenario replaces the current dataset and clears query history.
3. Imported data is deliberately constrained to 11 CSV fields: `record_id,date,region,province,item_id,item_name,category,customer_type,quantity,amount,profit`.
4. Local rule mode must keep working without an API key. AI is optional enrichment, not a prerequisite.
5. Action suggestions are not approved work. Only user-created action items are persisted; closing an action requires a non-empty review note.
6. Data imports and demo scenario loads create lineage records with source metadata and a SHA-256 fingerprint, but never duplicate uploaded CSV content for batch history.
5. No production authentication, RBAC, multi-tenancy, public deployment, or arbitrary-schema Text-to-SQL is implemented.

## Code map

| Location | Responsibility |
| --- | --- |
| `src/App.jsx` | Application state, navigation and async resources. |
| `src/views/` | Scenario, Query, Dashboard, Report, Anomaly, Forecast, Action and Config screens. |
| `src/components/AppShell.jsx` | Navigation, top command bar and status display. |
| `src/styles.css` | Apple-inspired premium light workspace styling; preserve responsive rules. |
| `src/lib/` | API client, downloads, formatting, request/history helpers and legacy UI utilities. |
| `backend/app/api/` | HTTP endpoints. |
| `backend/app/query/` | Controlled intent schemas, local parsing, SQL construction and query execution. |
| `backend/app/analytics/` | Dashboard, anomaly and forecast calculations. |
| `backend/app/reports/` | Modular report generation. |
| `backend/app/actions/` | Persisted decision-action creation, lifecycle validation and summary. |
| `backend/app/scenarios/` | Scenario catalog, activation and CSV import. |
| `backend/app/ai/` | Encrypted external AI configuration, validation, DeepSeek/OpenAI-compatible integration and fallback. |
| `backend/app/db/` | SQLAlchemy models, sessions and seed data. |
| `文档/` | All project, operation, demo and defense documents. |

## Important behaviors to preserve

- Query requests are only made after an explicit user action. Do not reintroduce query-on-render behavior.
- SQL must remain read-only, parameterized/controlled, and limited to approved metrics/dimensions.
- API errors are normalized with a safe error code/message and `request_id`; never echo sensitive input.
- AI keys are encrypted server-side, masked in responses and never committed. DeepSeek default UX should ask only for the key; other providers expose all fields.
- Local addresses and redirects are restricted unless the user explicitly allows private network access.
- Docker ports are loopback-only. Do not expose MySQL or the frontend to LAN by default.
- Tests use an isolated Compose project and data volume. Never make test reset or destroy the normal running database.
- Scenario questions are intentional product templates. Keep each scenario's terms, intent bindings, root-cause checks and recommendation actions aligned.

## API contract summary

- `GET /api/health`: application/database status, record count, AI mode and provider.
- `GET /api/metadata`: registered metric formulas/descriptions, filter values and current dataset coverage (`data_scope`).
- `POST /api/query`: `{ question }` -> safe SQL, rows, summary, chart recommendation and warnings.
- `GET /api/dashboard`: optional `region`, `category`, `customer_type` filters.
- `POST /api/reports/generate`: report type plus selected modules.
- `GET /api/anomalies`, `GET /api/forecast`: decision-support analysis.
- `GET/POST /api/actions`, `PATCH /api/actions/{id}`: human-confirmed action tracking; completion requires `review_notes`.
- `GET /api/scenarios`, `POST /api/scenarios/{id}/activate`, `POST /api/scenarios/import`: scenario library, recent data batch lineage and CSV replacement.
- `POST /api/scenarios/import/preview`: strict non-mutating CSV validation plus data coverage summary; use this before import.
- `GET/PUT/DELETE /api/settings/ai`, `POST /api/settings/ai/test`: optional AI configuration.

Use the live OpenAPI description at `http://localhost:8080/api/docs` instead of guessing request payload fields.

## Verification workflow

Run from repository root:

```powershell
npm.cmd test
npm.cmd run build
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

The full script is the release-level check. It runs isolated migrations, backend tests, frontend tests, production build, container checks and Playwright flows. For a local smoke check, start the system and call:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/health
```

## Documentation and delivery rules

- Put all new human-facing project material under `文档/`; do not recreate a `docs/` directory.
- Update `文档/系统设计说明书.md`, `文档/数据库与数据字典.md`, `文档/测试与验收报告.md`, and demo/defense material when changing a user-visible behavior.
- Preserve Chinese text as UTF-8 and keep links valid after any move.
- Never commit `.env`, generated secrets, real API keys, database volumes, or real business data.
- Before pushing, check `git status`, run targeted tests, then ensure the E-drive runnable copy is synchronized and built when the user asks for deployment.

## First places to inspect for a change

- UI wording/layout: `src/views/`, `src/components/`, then `src/styles.css`.
- Query meaning or SQL: `backend/app/scenarios/catalog.py`, `backend/app/query/`, and relevant tests.
- AI behavior: `backend/app/ai/`, `src/views/ConfigView.jsx`, then AI API tests.
- Data import/scenario behavior: `backend/app/scenarios/`, `backend/app/db/models.py`, scenario integration tests.
- Startup/deployment: `compose.yaml`, `docker/`, `scripts/`, and root `.cmd` files.
