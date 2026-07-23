# 智能 BI 数据洞察与报告生成平台

本仓库用于项目 11「智能 BI 数据洞察与报告生成平台」的需求分析、原型实现与后续开发准备。

项目面向企业经营分析和数据决策场景，目标是构建一个支持自然语言查询、自动报告生成、异常归因、趋势预测和可视化分析的智能 BI 平台。

## 30 秒开始演示

Windows 用户直接双击仓库根目录的 `启动智能BI系统.cmd`。启动器会在 Docker Desktop 未运行时尝试启动它，系统就绪后自动打开 `http://localhost:8080`。

首次启动需要 Docker Desktop 下载或构建镜像；之后日常启动会复用已有环境。应用启动后可直接体验本地规则模式，不需要填写任何 API Key。

- [系统功能演示文档](docs/DEMO_GUIDE.md)：逐步说明在什么位置输入什么内容。
- [演示素材包](docs/demo/README.md)：演示讲稿、问题清单和检查清单。
- [停止系统](停止智能BI系统.cmd)：正常停止服务，保留数据库数据。
- [API 文档](http://localhost:8080/api/docs)：系统运行后可访问。

## 文档

- [需求文档](docs/PRD.md)
- [项目 11 原始范围整理](docs/SOURCE_PROJECT_11.md)
- [2026-07-09 开发过程文档](docs/PROCESS_2026-07-09.md)
- [界面概念图](docs/assets/dashboard-concept.png)
- [功能演示文档](docs/DEMO_GUIDE.md)
- [演示素材包](docs/demo/README.md)

## Windows 本地运行

系统使用 Docker Compose 运行前端、FastAPI 后端和 MySQL 8.4。MySQL 不需要单独安装，端口只绑定到本机 `127.0.0.1:3307`，不会暴露到局域网。

### 前置条件

1. Windows 10/11，建议已启用 WSL 2。
2. Docker Desktop 已启动并显示 Engine running。
3. Node.js LTS（仅运行 `scripts/test.ps1` 时需要）。

未安装 Docker Desktop 时，在管理员或普通 PowerShell 中执行：

```powershell
winget install --exact --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
```

安装后打开 Docker Desktop。若提示启用 WSL 2 或重启，请按 Docker Desktop 提示完成后重启 Windows，再重新打开 Docker Desktop。可用以下命令确认环境：

```powershell
docker version
docker compose version
wsl --status
```

### 第一次启动和日常启动

在仓库根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

首次运行会原子地创建未跟踪的 `.env`，生成随机 MySQL 密码和 Fernet 主密钥，并构建、启动服务。已有 `.env` 不会被覆盖：脚本会保留现有值、密钥和文件编码；如果只缺少非敏感的 `QUERY_TIMEOUT_SECONDS` 或 `AI_DEFAULT_TIMEOUT_SECONDS`，会原子地补入默认值 `5` 和 `30`。其他必需配置或 Fernet 格式不正确时，脚本只显示需要处理的键名，不显示任何值。

启动脚本确认 `app=up`、`database=up` 且 `seeded_orders=540` 后输出访问地址：

- 应用：`http://localhost:8080`
- API 文档：`http://localhost:8080/api/docs`

### 停止、重置和测试

正常停止会保留 MySQL 数据卷：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

重置会先验证已解析的仓库根目录、固定的正常项目名和唯一允许删除的 `mysql_data` 卷，然后只删除该正常项目的 MySQL 数据卷并重新初始化 540 条示例订单。该操作不可恢复，必须显式确认：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\reset.ps1 -ConfirmReset
```

完整测试使用独立的固定 `-test` Compose 项目、独立 MySQL 数据卷和仅供测试的 `mock-llm`，不会读取或修改正常项目的数据库、卷或 AI 配置。测试期间由 Compose 启动生产构建的 Nginx 前端并映射到 `127.0.0.1:8081`，通过测试网络代理后端；Playwright 不会启动 Vite，也不会占用正常应用的 `8080`。它依次执行 Alembic、后端 Pytest、前端测试、Vite 构建、Nginx 容器构建和 Chrome 端到端验收，并在测试专用 MySQL/后端重启前后断言 540 条订单保持不变；无论成功、部分启动失败还是测试失败，都会清理整个测试项目及其测试卷。若缺少 `node_modules` 或前端工具，脚本会先按 `package-lock.json` 运行 `npm.cmd ci`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

端到端测试使用已安装的 Chrome 通道，不下载额外浏览器。默认地址为 `http://127.0.0.1:8081`；需要指向已启动的替代测试环境时，可设置 `PLAYWRIGHT_BASE_URL`，并保证该环境与测试数据库隔离。

### 本地规则模式和自有 AI API

默认使用本地规则引擎，因此不配置任何外部 API Key 也可演示仪表盘、查询、报告、异常和预测。配置页中的 OpenAI 兼容 API 是私有的自愿启用功能：仅当你主动保存 Base URL、Bearer API Key、模型名称和超时时才会启用。保存的 Key 由 `.env` 中的 Fernet 主密钥加密，接口和日志只返回脱敏状态，绝不会把 Key 返回给浏览器。

建议仅填入你拥有使用权限的 HTTPS OpenAI 兼容服务地址。若不再需要外部服务，可在配置页删除该配置并回到本地规则模式。

### 常见问题

- `Docker Desktop is not ready`：打开 Docker Desktop，等待引擎启动后重试；确认 `docker info` 成功。
- `docker` 不在 `PATH`：脚本会先使用 `Get-Command docker`，再尝试 Docker Desktop 标准位置 `C:\Program Files\Docker\Docker\resources\bin\docker.exe`。
- WSL 2 错误或 Docker 无法启动：执行 `wsl --status` 检查状态，按 Docker Desktop 的 WSL 集成提示安装或更新 WSL，必要时重启 Windows。
- 启动等待超时：执行 `docker compose ps`，然后根据服务查看 `docker compose logs backend` 或 `docker compose logs mysql`。
- `.env` 校验失败：按报出的键名补全或修正 `.env`；脚本不会替换已存在的密码、主密钥或任何自有 API 配置。

### 安全边界

`.env`、数据库卷、日志和构建输出均不纳入 Git。不要把 `.env`、截图中的密钥或自有 API Key 发到仓库、工单或聊天记录。正常运行、停止和重置都固定到本仓库的 Compose 文件和正常项目名；测试固定到独立测试 Compose 文件和项目名，外部 `COMPOSE_FILE` 或 `COMPOSE_PROJECT_NAME` 不会改变目标。Compose 发布端口仅监听 `127.0.0.1`，但本机账户仍应受到操作系统保护。

## 核心能力

- 自然语言转 SQL 查询
- 多维数据下钻与可视化展示
- 周报、月报和自定义报告生成
- 关键业务指标异常检测与归因分析
- 销量、收入等指标趋势预测
- 假设分析和业务模拟

## 技术方向

PDF 项目说明中给出的技术方向包括：

- AI 核心：Python、Text-to-SQL、大模型、Agent 技术
- 前端：Vue.js
- 数据库：MySQL 8.0
- 服务与部署：Nginx

当前版本使用 React + Vite 构建前端，由 Nginx 提供静态资源和 `/api` 代理；FastAPI 提供查询、报告、异常、预测和 AI 配置接口，MySQL 8.4 保存业务数据、指标、模板、查询历史和加密配置。
