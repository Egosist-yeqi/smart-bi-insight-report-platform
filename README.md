# 智能 BI 数据洞察与报告生成平台

本仓库用于项目 11「智能 BI 数据洞察与报告生成平台」的需求分析、原型实现与后续开发准备。

项目面向企业经营分析和数据决策场景，目标是构建一个支持自然语言查询、自动报告生成、异常归因、趋势预测和可视化分析的智能 BI 平台。

## 文档

- [需求文档](docs/PRD.md)
- [项目 11 原始范围整理](docs/SOURCE_PROJECT_11.md)
- [2026-07-09 开发过程文档](docs/PROCESS_2026-07-09.md)
- [界面概念图](docs/assets/dashboard-concept.png)

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

首次运行会原子地创建未跟踪的 `.env`，生成随机 MySQL 密码和 Fernet 主密钥，并构建、启动服务。已有 `.env` 不会被覆盖；脚本只会校验必需键名、超时配置和 Fernet 格式，并以不显示值的错误提示需要补充的配置。

启动脚本确认 `app=up`、`database=up` 且 `seeded_orders=540` 后输出访问地址：

- 应用：`http://localhost:8080`
- API 文档：`http://localhost:8080/api/docs`

### 停止、重置和测试

正常停止会保留 MySQL 数据卷：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

重置会删除本 Compose 项目的 MySQL 数据卷并重新初始化 540 条示例订单。该操作不可恢复，必须显式确认：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\reset.ps1 -ConfirmReset
```

完整测试会启动 MySQL 和仅用于测试的 `mock-llm`，执行 Alembic、后端 Pytest、前端测试和构建。无论成功或失败，脚本都会清理测试专用 `mock-llm` 容器，不会删除默认 MySQL 数据卷：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

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

`.env`、数据库卷、日志和构建输出均不纳入 Git。不要把 `.env`、截图中的密钥或自有 API Key 发到仓库、工单或聊天记录。Compose 发布端口仅监听 `127.0.0.1`，但本机账户仍应受到操作系统保护。

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

当前版本先实现 React + Vite 前端原型和本地演示数据闭环。后续建议补充 FastAPI 作为 Python 后端接口层，将真实 Text-to-SQL、报告生成、异常分析和预测能力封装为可调用服务，并接入 MySQL 8.0。
