import React from 'react';
import AsyncPanel from '../components/AsyncPanel.jsx';
import DataTable from '../components/DataTable.jsx';
import { BarChart, LineChart } from '../components/Charts.jsx';
import { downloadText, rowsToCsv } from '../lib/downloads.js';
import { prepareQueryHistory, QUERY_HISTORY_LIMIT } from '../lib/queryHistory.js';

const sampleQuestions = [
  '上月华东区销售额最高的产品是什么？', '本月各区域销售额排名如何？',
  '最近30天销售额趋势如何？', '哪个产品类别的毛利最高？',
  '本周订单量相比上周下降了吗？', '为什么本月华南区销售额出现下降？',
  '下个月销售额可能是多少？', '如果华东区促销投入增加10%，价格下降5%，销售额会怎样？',
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

export default function QueryView({ question, setQuestion, submitQuestion, resource, historyResource }) {
  return (
    <section className="workspace">
      <div className="panel panel--span-7">
        <div className="panel-header"><div><h2>自然语言查询</h2><p>选择示例问题或输入自定义问题，系统会解析意图并生成只读 SQL。</p></div></div>
        <div className="sample-grid">
          {sampleQuestions.map((sample) => <button key={sample} type="button" onClick={() => { setQuestion(sample); submitQuestion(sample); }}>{sample}</button>)}
        </div>
        <AsyncPanel resource={resource} minHeight={248}>{(response) => {
          const result = response?.data;
          if (!result) return <div className="empty-state">输入问题后运行查询</div>;
          return <div className="query-result">
            {result.warning ? <div className="analysis-warning" role="status"><strong>{result.warning.message}</strong><span>{result.warning.code}</span></div> : null}
            <div className="result-summary"><span>{result.data_period || result.query_period}</span><strong>{result.summary}</strong><small>{provenanceText(result)}</small></div>
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
