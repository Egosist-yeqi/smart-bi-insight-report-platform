import React, { useMemo, useState } from 'react';
import MetricCard from './components/MetricCard.jsx';
import DataTable from './components/DataTable.jsx';
import { BarChart, ContributionGrid, LineChart } from './components/Charts.jsx';
import { latestMonth, metricDefinitions, reportModules, salesRecords } from './data/sampleData.js';
import { filterRecords, getKpiDeltas, monthlyTrend, toCsv, weeklyTrend } from './lib/analytics.js';
import { formatCurrency, formatDelta, formatNumber, formatPercent } from './lib/formatters.js';
import { generateReport } from './lib/reporting.js';
import { getDashboardSnapshot, runNaturalLanguageQuery } from './lib/queryEngine.js';

const navItems = ['智能查询', '仪表盘', '报告生成', '异常归因', '趋势预测', '系统配置'];
const sampleQuestions = [
  '上月华东区销售额最高的产品是什么？',
  '本月各区域销售额排名如何？',
  '最近30天销售额趋势如何？',
  '哪个产品类别的毛利最高？',
  '本周订单量相比上周下降了吗？',
  '为什么本月华南区销售额出现下降？',
  '下个月销售额可能是多少？',
  '如果华东区促销投入增加10%，价格下降5%，销售额会怎样？',
];

const defaultModules = ['overview', 'region', 'ranking', 'anomaly', 'forecast'];

function downloadText(filename, content, mime = 'text/plain;charset=utf-8') {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function AppShell({ active, setActive, children }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark">BI</span>
          <div>
            <strong>智能 BI</strong>
            <small>数据洞察平台</small>
          </div>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              className={active === item ? 'nav-item nav-item--active' : 'nav-item'}
              key={item}
              onClick={() => setActive(item)}
              type="button"
            >
              {item}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span>演示数据集</span>
          <strong>{latestMonth}</strong>
          <small>销售订单 · 区域 · 产品 · 客户类型</small>
        </div>
      </aside>
      <main className="main-panel">{children}</main>
    </div>
  );
}

function TopBar({ question, setQuestion, onRun }) {
  return (
    <header className="topbar">
      <div>
        <h1>智能 BI 数据洞察与报告生成平台</h1>
        <p>自然语言查询、Text-to-SQL、异常归因、预测和报告输出的一体化原型。</p>
      </div>
      <form className="command-bar" onSubmit={(event) => { event.preventDefault(); onRun(); }}>
        <input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="输入经营分析问题" />
        <button type="submit">运行查询</button>
      </form>
    </header>
  );
}

function QueryWorkbench({ question, setQuestion, result, onRun, setResult }) {
  const chartData = result.rows || [];

  return (
    <section className="workspace">
      <div className="panel panel--span-7">
        <div className="panel-header">
          <div>
            <h2>自然语言查询</h2>
            <p>选择示例问题或输入自定义问题，系统会解析意图并生成只读 SQL。</p>
          </div>
          <span className={result.safe ? 'status status--safe' : 'status status--warn'}>{result.safe ? '只读 SQL' : '需人工复核'}</span>
        </div>
        <div className="sample-grid">
          {sampleQuestions.map((sample) => (
            <button
              key={sample}
              type="button"
              onClick={() => {
                setQuestion(sample);
                setResult(runNaturalLanguageQuery(sample, salesRecords));
              }}
            >
              {sample}
            </button>
          ))}
        </div>
        <div className="query-result">
          <div className="result-summary">
            <span>{result.intent}</span>
            <strong>{result.summary}</strong>
            <small>{result.explanation}</small>
          </div>
          <pre className="sql-box">{result.sql}</pre>
          <div className="actions-row">
            <button type="button" onClick={onRun}>重新运行</button>
            <button type="button" onClick={() => downloadText('query-result.csv', toCsv(result.rows), 'text/csv;charset=utf-8')}>导出 CSV</button>
          </div>
        </div>
      </div>

      <div className="panel panel--span-5">
        <div className="panel-header">
          <h2>推荐图表</h2>
          <span>置信度 {(result.confidence * 100).toFixed(0)}%</span>
        </div>
        {result.chartType === 'line'
          ? <LineChart data={chartData.map((row) => ({ ...row, name: row.name || row.label }))} />
          : <BarChart data={chartData.map((row) => ({ ...row, name: row.name || row.region || row.label || row.intent }))} />}
      </div>

      <div className="panel panel--span-12">
        <div className="panel-header">
          <h2>结果表</h2>
          <span>自动匹配业务指标与维度</span>
        </div>
        <DataTable rows={result.rows} />
      </div>
    </section>
  );
}

function DashboardView() {
  const [filters, setFilters] = useState({ region: '全部', category: '全部', customerType: '全部' });
  const snapshot = useMemo(() => getDashboardSnapshot(salesRecords), []);
  const deltas = useMemo(() => getKpiDeltas(salesRecords), []);
  const filteredRecords = filterRecords(salesRecords, { month: latestMonth, ...filters });
  const filteredSnapshot = getDashboardSnapshot(filteredRecords.length ? filteredRecords : salesRecords);
  const trend = monthlyTrend(salesRecords);

  return (
    <section className="workspace">
      <div className="filter-strip panel panel--span-12">
        {['region', 'category', 'customerType'].map((key) => {
          const labelMap = { region: '区域', category: '类别', customerType: '客户类型' };
          const values = ['全部', ...new Set(salesRecords.map((record) => record[key]))];
          return (
            <label key={key}>
              {labelMap[key]}
              <select value={filters[key]} onChange={(event) => setFilters({ ...filters, [key]: event.target.value })}>
                {values.map((value) => <option key={value}>{value}</option>)}
              </select>
            </label>
          );
        })}
        <button type="button" onClick={() => setFilters({ region: '全部', category: '全部', customerType: '全部' })}>清空筛选</button>
      </div>

      <div className="metrics-row panel--span-12">
        <MetricCard label="销售额" value={snapshot.kpis.amount} delta={deltas.amount} type="currency" note="较上月" />
        <MetricCard label="销售数量" value={snapshot.kpis.quantity} delta={deltas.quantity} note="较上月" />
        <MetricCard label="客单价" value={snapshot.kpis.avgOrderValue} delta={deltas.avgOrderValue} type="currency" note="较上月" />
        <MetricCard label="毛利率" value={snapshot.kpis.profitRate} delta={deltas.profitRate} type="percent" note="百分点" />
      </div>

      <div className="panel panel--span-7">
        <div className="panel-header">
          <h2>销售趋势</h2>
          <span>月度聚合</span>
        </div>
        <LineChart data={trend} />
      </div>
      <div className="panel panel--span-5">
        <div className="panel-header">
          <h2>区域贡献</h2>
          <span>支持下钻</span>
        </div>
        <BarChart data={filteredSnapshot.regions} />
      </div>
      <div className="panel panel--span-7">
        <div className="panel-header">
          <h2>产品排行</h2>
          <span>{filters.region === '全部' ? '全区域' : filters.region}</span>
        </div>
        <ContributionGrid rows={filteredSnapshot.products.slice(0, 5)} />
      </div>
      <div className="panel panel--span-5">
        <div className="panel-header">
          <h2>异常提醒</h2>
          <span>{snapshot.anomalies.length} 条</span>
        </div>
        <div className="insight-list">
          {snapshot.anomalies.map((item) => (
            <article key={item.region}>
              <span>{item.level}</span>
              <strong>{item.region} {formatDelta(item.delta)}</strong>
              <p>{item.reason}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function ReportView() {
  const [type, setType] = useState('月报');
  const [modules, setModules] = useState(defaultModules);
  const report = useMemo(() => generateReport(salesRecords, { type, modules }), [type, modules]);

  function toggleModule(moduleId) {
    setModules((current) => current.includes(moduleId)
      ? current.filter((id) => id !== moduleId)
      : [...current, moduleId]);
  }

  return (
    <section className="workspace">
      <div className="panel panel--span-4">
        <div className="panel-header">
          <h2>报告配置</h2>
          <span>模板驱动</span>
        </div>
        <label className="field-label">
          报告类型
          <select value={type} onChange={(event) => setType(event.target.value)}>
            <option>周报</option>
            <option>月报</option>
            <option>自定义报告</option>
          </select>
        </label>
        <div className="check-list">
          {reportModules.map((module) => (
            <label key={module.id}>
              <input type="checkbox" checked={modules.includes(module.id)} onChange={() => toggleModule(module.id)} />
              {module.label}
            </label>
          ))}
        </div>
        <button type="button" onClick={() => downloadText(`${latestMonth}-智能BI经营分析报告.md`, report.markdown, 'text/markdown;charset=utf-8')}>导出 Markdown</button>
      </div>
      <div className="panel panel--span-8">
        <div className="panel-header">
          <h2>{report.title}</h2>
          <span>报告预览</span>
        </div>
        <div className="report-preview">
          {report.sections.map((section) => (
            <article key={section.title}>
              <h3>{section.title}</h3>
              <p>{section.content}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function AnomalyView() {
  const snapshot = getDashboardSnapshot(salesRecords);

  return (
    <section className="workspace">
      <div className="panel panel--span-7">
        <div className="panel-header">
          <h2>指标异动监控</h2>
          <span>阈值 18%</span>
        </div>
        <DataTable rows={snapshot.anomalies} />
      </div>
      <div className="panel panel--span-5">
        <div className="panel-header">
          <h2>维度归因</h2>
          <span>区域 / 产品 / 客户</span>
        </div>
        <BarChart data={snapshot.regions} formatter={formatCurrency} />
        <p className="panel-note">说明区分数据支持结论与系统推测：区域变化来自上月对比，具体经营原因需要继续接入渠道、促销和库存数据。</p>
      </div>
    </section>
  );
}

function ForecastView() {
  const snapshot = getDashboardSnapshot(salesRecords);
  const weekly = weeklyTrend(salesRecords.filter((record) => record.month === latestMonth));

  return (
    <section className="workspace">
      <div className="panel panel--span-8">
        <div className="panel-header">
          <h2>趋势预测</h2>
          <span>{snapshot.forecast.label}</span>
        </div>
        <LineChart data={[...monthlyTrend(salesRecords), { name: snapshot.forecast.label, amount: snapshot.forecast.predictedAmount }]} />
        <p className="panel-note">{snapshot.forecast.basis} 预测仅供参考。</p>
      </div>
      <div className="panel panel--span-4">
        <div className="panel-header">
          <h2>假设分析</h2>
          <span>促销 + 价格</span>
        </div>
        <strong className="forecast-number">{formatCurrency(snapshot.forecast.predictedAmount)}</strong>
        <p className="panel-note">如果华东区促销投入增加 10%、价格下降 5%，系统会按演示弹性估算净影响并给出解释。</p>
        <DataTable rows={[{ label: '最近周销售', amount: weekly.at(-1).amount, quantity: weekly.at(-1).quantity }]} />
      </div>
    </section>
  );
}

function ConfigView() {
  return (
    <section className="workspace">
      <div className="panel panel--span-7">
        <div className="panel-header">
          <h2>指标字典</h2>
          <span>{metricDefinitions.length} 项</span>
        </div>
        <DataTable rows={metricDefinitions.map((metric) => ({
          name: metric.name,
          code: metric.code,
          formula: metric.formula,
          description: metric.description,
        }))} />
      </div>
      <div className="panel panel--span-5">
        <div className="panel-header">
          <h2>数据源状态</h2>
          <span>演示模式</span>
        </div>
        <div className="source-box">
          <strong>sales_order</strong>
          <span>{salesRecords.length} 条演示订单批次</span>
          <small>字段覆盖订单日期、区域、产品、客户类型、销售数量、销售额和毛利。</small>
        </div>
      </div>
    </section>
  );
}

export default function App() {
  const [active, setActive] = useState('智能查询');
  const [question, setQuestion] = useState(sampleQuestions[0]);
  const [result, setResult] = useState(() => runNaturalLanguageQuery(sampleQuestions[0], salesRecords));

  function runQuery() {
    setActive('智能查询');
    setResult(runNaturalLanguageQuery(question, salesRecords));
  }

  let content;
  if (active === '智能查询') content = <QueryWorkbench question={question} setQuestion={setQuestion} result={result} onRun={runQuery} setResult={setResult} />;
  if (active === '仪表盘') content = <DashboardView />;
  if (active === '报告生成') content = <ReportView />;
  if (active === '异常归因') content = <AnomalyView />;
  if (active === '趋势预测') content = <ForecastView />;
  if (active === '系统配置') content = <ConfigView />;

  return (
    <AppShell active={active} setActive={setActive}>
      <TopBar question={question} setQuestion={setQuestion} onRun={runQuery} />
      {content}
    </AppShell>
  );
}
