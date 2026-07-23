import React from 'react';
import AsyncPanel from '../components/AsyncPanel.jsx';
import DataTable from '../components/DataTable.jsx';
import { BarChart, LineChart } from '../components/Charts.jsx';
import { downloadText, rowsToCsv } from '../lib/downloads.js';
import { prepareQueryHistory, QUERY_HISTORY_LIMIT } from '../lib/queryHistory.js';
import { formatCurrency, formatPercent } from '../lib/formatters.js';

const sampleQuestionGroups = [
  { title: '发生了什么', questions: ['本月各区域销售额排名如何？', '本周订单量相比上周下降了吗？', '最近30天销售额趋势如何？'] },
  { title: '为什么发生', questions: ['为什么本月华南区销售额出现下降？', '哪个产品类别的毛利最高？', '上月华东区销售额最高的产品是什么？'] },
  { title: '接下来怎么办', questions: ['本月经营上最需要优先关注哪个区域？', '华南区销售下降后应优先采取什么措施？'] },
  { title: '预测与模拟', questions: ['下个月销售额可能是多少？', '如果华东区促销投入增加10%，价格下降5%，销售额会怎样？'] },
];

function chartRows(result) {
  return (result.rows || []).map((row, index) => ({
    ...row,
    name: row.name || row.region || row.product_name || row.month || row.week || `结果 ${index + 1}`,
    amount: row.amount ?? row.metric_value ?? row.simulated_amount ?? 0,
  }));
}

function provenanceText(result) {
  if (result.provenance === 'local_fallback') return '本地回退结果已通过只读 SQL 校验。';
  if (result.provenance === 'local') return 'AI 未启用；本地规则解析结果已通过只读 SQL 校验。';
  return 'AI 解析结果已通过只读 SQL 校验。';
}

function DecisionCard({ answer }) {
  if (!answer || answer.unavailable) return null;
  if (answer.kind === 'promotion_scenario') {
    return <article className="decision-card"><div><span>情景预测</span><strong>{formatCurrency(answer.simulated_amount)}</strong></div><p>以 {formatCurrency(answer.base_amount)} 为基准；促销投入增加 {formatPercent(answer.assumptions.promotion_increase)}、价格下降 {formatPercent(answer.assumptions.price_drop)}，演示模型估算净影响 {formatPercent(answer.net_change)}。</p><small>弹性假设仅用于模拟，需结合毛利和转化数据验证。</small></article>;
  }
  if (answer.kind === 'forecast' && answer.prediction) {
    return <article className="decision-card"><div><span>趋势预测</span><strong>{formatCurrency(answer.prediction.amount)}</strong></div><p>预测月份：{String(answer.prediction.month).slice(0, 7)}。{answer.prediction.basis}</p><small>预测基于历史趋势，不代表实际经营承诺。</small></article>;
  }
  if (answer.kind === 'root_cause') {
    return <article className="decision-card"><div><span>变化归因线索</span><strong>{formatPercent(answer.percent_change)}</strong></div><p>{answer.current.month} 相比 {answer.previous.month} {answer.direction}，需要优先核查：</p><ul>{answer.checks.map((item) => <li key={item}>{item}</li>)}</ul><small>以上为数据驱动的核查方向，不将相关性直接认定为因果。</small></article>;
  }
  if (answer.kind === 'recommendation') {
    return <article className="decision-card"><div><span>行动建议</span><strong>{answer.region}</strong></div><p>当前月销售额：{formatCurrency(answer.current_amount)}</p><ol>{answer.actions.map((item) => <li key={item}>{item}</li>)}</ol><small>{answer.guardrail}</small></article>;
  }
  return null;
}

function historyTime(value) {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) return '时间未知';
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

function QueryHistory({ resource }) {
  let content;
  if (resource.loading) {
    content = <div className="query-history__state" role="status">正在加载查询历史...</div>;
  } else if (resource.error) {
    content = <div className="query-history__state query-history__state--error" role="alert"><strong>{resource.error.message || '查询历史加载失败。'}</strong><button type="button" onClick={resource.reload}>重试</button></div>;
  } else {
    const records = prepareQueryHistory(resource.data?.data);
    content = records.length ? <div className="query-history__list">{records.map((record, index) => (
      <div className="query-history__item" key={`${record.createdAt}-${record.question}-${index}`}>
        <div className="query-history__identity">
          <strong className="query-history__question">{record.question}</strong>
          <div className="query-history__meta">
            <span className="query-history__engine">{record.engine === 'ai' ? 'AI' : '本地'}</span>
            <span className={`query-history__status query-history__status--${record.status}`}>{record.status === 'succeeded' ? '成功' : '失败'}</span>
          </div>
        </div>
        <p className="query-history__summary">{record.summary || (record.status === 'failed' ? '查询未完成' : '暂无摘要')}</p>
        <time dateTime={record.createdAt}>{historyTime(record.createdAt)}</time>
      </div>
    ))}</div> : <div className="query-history__state query-history__state--empty">暂无查询历史</div>;
  }

  return <div className="panel panel--span-12 query-history">
    <div className="panel-header"><h2>查询历史</h2><span>最近 {QUERY_HISTORY_LIMIT} 条</span></div>
    {content}
  </div>;
}

export default function QueryView({ scenario, question, setQuestion, submitQuestion, resource, historyResource }) {
  const questionGroups = scenario?.question_groups || sampleQuestionGroups;
  return (
    <section className="workspace">
      <div className="panel panel--span-7">
        <div className="panel-header"><div><h2>自然语言查询</h2><p>选择示例问题或输入自定义问题，系统会解析意图并生成只读 SQL。</p></div></div>
        <div className="decision-question-groups">
          {questionGroups.map((group) => <div className="decision-question-group" key={group.title}><h3>{group.title}</h3><div className="sample-grid">{group.questions.map((sample) => <button key={sample} type="button" onClick={() => { setQuestion(sample); submitQuestion(sample); }}>{sample}</button>)}</div></div>)}
        </div>
        <AsyncPanel resource={resource} minHeight={248}>{(response) => {
          const result = response?.data;
          if (!result) return <div className="empty-state">输入问题后运行查询</div>;
          return <div className="query-result">
            {result.warning ? <div className="analysis-warning" role="status"><strong>{result.warning.message}</strong><span>{result.warning.code}</span></div> : null}
            <div className="result-summary"><span>{result.data_period || result.query_period}</span><strong>{result.summary}</strong><small>{provenanceText(result)}</small></div>
            <DecisionCard answer={result.answer} />
            <pre className="sql-box">{result.sql}</pre>
            <div className="actions-row"><button type="button" onClick={() => submitQuestion(question)}>重新运行</button><button type="button" onClick={() => downloadText('query-result.csv', rowsToCsv(result.rows), 'text/csv;charset=utf-8')}>导出 CSV</button></div>
          </div>;
        }}</AsyncPanel>
      </div>
      <div className="panel panel--span-5">
        <div className="panel-header"><h2>推荐图表</h2><span>按查询意图匹配</span></div>
        <AsyncPanel resource={resource} minHeight={248}>{(response) => {
          const result = response?.data;
          const rows = result ? chartRows(result) : [];
          return rows.length ? (result.chart_type === 'line' ? <LineChart data={rows} /> : <BarChart data={rows} />) : <div className="empty-state">暂无可视化结果</div>;
        }}</AsyncPanel>
      </div>
      <div className="panel panel--span-12">
        <div className="panel-header"><h2>结果表</h2><span>自动匹配业务指标与维度</span></div>
        <AsyncPanel resource={resource} minHeight={220}>{(response) => <DataTable rows={response?.data?.rows || []} />}</AsyncPanel>
      </div>
      <QueryHistory resource={historyResource} />
    </section>
  );
}
