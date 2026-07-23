import React from 'react';
import AsyncPanel from '../components/AsyncPanel.jsx';
import DataTable from '../components/DataTable.jsx';
import { BarChart } from '../components/Charts.jsx';
import { apiClient } from '../lib/apiClient.js';
import { useAsync } from '../hooks/useAsync.js';

export default function AnomalyView({ scenario }) {
  const anomalies = useAsync((signal) => apiClient.anomalies({ signal }), []);
  const dashboard = useAsync((signal) => apiClient.dashboard({}, { signal }), []);
  return <section className="workspace"><div className="panel panel--span-7"><div className="panel-header"><h2>{scenario?.amount_label || '销售额'}异动监控</h2><span>阈值 18%</span></div><AsyncPanel resource={anomalies} minHeight={300}>{(response) => <DataTable rows={response?.data?.items || []} />}</AsyncPanel></div><div className="panel panel--span-5"><div className="panel-header"><h2>维度归因</h2><span>组织 / {scenario?.entity_label || '产品'} / 对象</span></div><AsyncPanel resource={dashboard} minHeight={300}>{(response) => <>{response?.data?.regions?.length ? <BarChart data={response.data.regions} /> : <div className="empty-state">暂无组织归因数据</div>}<p className="panel-note">组织变化来自已完成月度聚合；具体经营原因需要继续核查项目组合、对象明细与执行节奏。</p></>}</AsyncPanel></div></section>;
}
