import React, { useState } from 'react';
import AppShell from './components/AppShell.jsx';
import { useAsync } from './hooks/useAsync.js';
import { apiClient } from './lib/apiClient.js';
import QueryView from './views/QueryView.jsx';
import DashboardView from './views/DashboardView.jsx';
import ReportView from './views/ReportView.jsx';
import AnomalyView from './views/AnomalyView.jsx';
import ForecastView from './views/ForecastView.jsx';
import ConfigView from './views/ConfigView.jsx';

const firstQuestion = '上月华东区销售额最高的产品是什么？';

export default function App() {
  const [active, setActive] = useState('智能查询');
  const [question, setQuestion] = useState(firstQuestion);
  const [queryRequest, setQueryRequest] = useState({ question: firstQuestion });
  const health = useAsync((signal) => apiClient.health({ signal }), []);
  const provider = useAsync((signal) => apiClient.getAi({ signal }), []);
  const query = useAsync((signal) => apiClient.query(queryRequest.question, { signal }), [queryRequest]);
  const runQuery = (value = question) => { if (!value.trim()) return; setActive('智能查询'); setQueryRequest({ question: value.trim() }); };

  const views = {
    '智能查询': <QueryView question={question} setQuestion={setQuestion} submitQuestion={runQuery} resource={query} />,
    仪表盘: <DashboardView />,
    报告生成: <ReportView />,
    异常归因: <AnomalyView />,
    趋势预测: <ForecastView />,
    系统配置: <ConfigView onProviderChange={() => { provider.reload(); health.reload(); }} />,
  };

  return <AppShell active={active} setActive={setActive} question={question} setQuestion={setQuestion} onRun={runQuery} healthResource={health} onRefreshStatus={() => { health.reload(); provider.reload(); }} provider={provider.data?.data}>{views[active]}</AppShell>;
}
