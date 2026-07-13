import React from 'react';
import AsyncPanel from '../components/AsyncPanel.jsx';
import DataTable from '../components/DataTable.jsx';
import { BarChart } from '../components/Charts.jsx';
import { apiClient } from '../lib/apiClient.js';
import { useAsync } from '../hooks/useAsync.js';

export default function AnomalyView() {
  const anomalies = useAsync((signal) => apiClient.anomalies({ signal }), []);
  const dashboard = useAsync((signal) => apiClient.dashboard({}, { signal }), []);
  return <section className="workspace"><div className="panel panel--span-7"><div className="panel-header"><h2>指标异动监控</h2><span>阈值 18%</span></div><AsyncPanel resource={anomalies} minHeight={300}>{(response) => <DataTable rows={response?.data?.items || []} />}</AsyncPanel></div><div className="panel panel--span-5"><div className="panel-header"><h2>维度归因</h2><span>区域 / 产品 / 客户</span></div><AsyncPanel resource={dashboard} minHeight={300}>{(response) => <>{response?.data?.regions?.length ? <BarChart data={response.data.regions} /> : <div className="empty-state">暂无区域归因数据</div>}<p className="panel-note">区域变化来自已完成月度订单聚合；具体经营原因需要继续核查产品组合、客户订单与出货节奏。</p></>}</AsyncPanel></div></section>;
}
