import React, { useState } from 'react';
import AsyncPanel from '../components/AsyncPanel.jsx';
import MetricCard from '../components/MetricCard.jsx';
import { BarChart, ContributionGrid, LineChart } from '../components/Charts.jsx';
import { formatDelta } from '../lib/formatters.js';
import { apiClient } from '../lib/apiClient.js';
import { useAsync } from '../hooks/useAsync.js';

const defaults = { region: '全部', category: '全部', customerType: '全部' };
const labels = { region: '区域', category: '类别', customerType: '客户类型' };
const metadataKeys = { region: 'regions', category: 'categories', customerType: 'customer_types' };

export default function DashboardView() {
  const [filters, setFilters] = useState(defaults);
  const metadata = useAsync((signal) => apiClient.metadata({ signal }), []);
  const dashboard = useAsync((signal) => apiClient.dashboard(filters, { signal }), [filters.region, filters.category, filters.customerType]);
  const anomalies = useAsync((signal) => apiClient.anomalies({ signal }), []);

  return <section className="workspace">
    <div className="filter-strip panel panel--span-12">
      {Object.keys(labels).map((key) => {
        const values = metadata.data?.data?.[metadataKeys[key]] || [];
        return <label key={key}>{labels[key]}<select value={filters[key]} onChange={(event) => setFilters({ ...filters, [key]: event.target.value })}><option>全部</option>{values.map((value) => <option key={value}>{value}</option>)}</select></label>;
      })}
      <button type="button" onClick={() => setFilters(defaults)}>清空筛选</button>
    </div>
    <AsyncPanel resource={dashboard} minHeight={560}>{(response) => {
      const data = response?.data;
      if (!data) return <div className="panel panel--span-12 empty-state">暂无仪表盘数据</div>;
      const trend = data.trend.map((point) => ({ ...point, name: String(point.month).slice(0, 7) }));
      return <>
        <div className="metrics-row panel--span-12"><MetricCard label="销售额" value={data.kpis.amount} delta={data.deltas.amount} type="currency" note="较上月" /><MetricCard label="销售数量" value={data.kpis.quantity} delta={data.deltas.quantity} note="较上月" /><MetricCard label="客单价" value={data.kpis.avg_order_value} delta={data.deltas.avg_order_value} type="currency" note="较上月" /><MetricCard label="毛利率" value={data.kpis.profit_rate} delta={data.deltas.profit_rate} type="percent" note="百分点" /></div>
        <div className="panel panel--span-7"><div className="panel-header"><h2>销售趋势</h2><span>月度聚合</span></div><LineChart data={trend} /></div>
        <div className="panel panel--span-5"><div className="panel-header"><h2>区域贡献</h2><span>支持下钻</span></div><BarChart data={data.regions} /></div>
        <div className="panel panel--span-7"><div className="panel-header"><h2>产品排行</h2><span>{filters.region === '全部' ? '全区域' : filters.region}</span></div><ContributionGrid rows={data.products.slice(0, 5)} /></div>
        <div className="panel panel--span-5"><div className="panel-header"><h2>异常提醒</h2><span>{anomalies.data?.data?.items?.length || 0} 条</span></div><AsyncPanel resource={anomalies} minHeight={180}>{(anomalyResponse) => <div className="insight-list">{(anomalyResponse?.data?.items || []).map((item) => <article key={item.region}><span>{item.level}</span><strong>{item.region} {formatDelta(item.delta)}</strong><p>{item.evidence}</p></article>)}{!anomalyResponse?.data?.items?.length && <div className="empty-state">暂无达到阈值的异常</div>}</div>}</AsyncPanel></div>
      </>;
    }}</AsyncPanel>
  </section>;
}
