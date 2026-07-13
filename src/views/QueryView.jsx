import React from 'react';
import AsyncPanel from '../components/AsyncPanel.jsx';
import DataTable from '../components/DataTable.jsx';
import { BarChart, LineChart } from '../components/Charts.jsx';
import { downloadText, rowsToCsv } from '../lib/downloads.js';

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

export default function QueryView({ question, setQuestion, submitQuestion, resource }) {
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
            <div className="result-summary"><span>{result.data_period || result.query_period}</span><strong>{result.summary}</strong><small>{result.engine === 'ai' ? 'AI 解析结果已通过只读 SQL 校验。' : '本地规则解析结果已通过只读 SQL 校验。'}</small></div>
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
    </section>
  );
}
