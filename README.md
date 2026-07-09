# 智能 BI 数据洞察与报告生成平台

本仓库用于项目 11「智能 BI 数据洞察与报告生成平台」的需求分析、原型实现与后续开发准备。

项目面向企业经营分析和数据决策场景，目标是构建一个支持自然语言查询、自动报告生成、异常归因、趋势预测和可视化分析的智能 BI 平台。

## 文档

- [需求文档](docs/PRD.md)
- [项目 11 原始范围整理](docs/SOURCE_PROJECT_11.md)
- [2026-07-09 开发过程文档](docs/PROCESS_2026-07-09.md)
- [界面概念图](docs/assets/dashboard-concept.png)

## 运行方式

```bash
npm.cmd install
npm.cmd run dev
```

开发服务器默认运行在 `http://127.0.0.1:5173/`。

## 验证命令

```bash
npm.cmd test
npm.cmd run build
```

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
