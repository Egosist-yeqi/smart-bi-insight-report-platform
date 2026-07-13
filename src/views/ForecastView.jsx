import React from 'react';
import AsyncPanel from '../components/AsyncPanel.jsx';
import DataTable from '../components/DataTable.jsx';
import { LineChart } from '../components/Charts.jsx';
import { apiClient } from '../lib/apiClient.js';
import { useAsync } from '../hooks/useAsync.js';
import { formatCurrency } from '../lib/formatters.js';

export default function ForecastView() {
  const forecast = useAsync((signal) => apiClient.forecast({ signal }), []);
  return <section className="workspace"><AsyncPanel resource={forecast} minHeight={420}>{(response) => { const data = response?.data; const prediction = data?.prediction; const history = (data?.history || []).map((item) => ({ ...item, name: String(item.month).slice(0, 7) })); return <><div className="panel panel--span-8"><div className="panel-header"><h2>趋势预测</h2><span>{prediction ? String(prediction.month).slice(0, 7) : '暂无预测'}</span></div>{history.length ? <LineChart data={prediction ? [...history, { ...prediction, name: String(prediction.month).slice(0, 7) }] : history} /> : <div className="empty-state">暂无历史数据</div>}<p className="panel-note">{prediction?.basis || '历史数据不足，暂无法生成下月预测。'} 预测仅供参考。</p></div><div className="panel panel--span-4"><div className="panel-header"><h2>预测摘要</h2><span>OLS 线性回归</span></div><strong className="forecast-number">{prediction ? formatCurrency(prediction.amount) : '-'}</strong><p className="panel-note">预测值基于已完成月度销售额趋势，不代表实际业务承诺。</p><DataTable rows={prediction ? [{ month: prediction.month, amount: prediction.amount, is_estimate: prediction.is_estimate }] : []} /></div></>; }}</AsyncPanel></section>;
}
