import React, { useState } from 'react';
import AsyncPanel from '../components/AsyncPanel.jsx';
import { apiClient } from '../lib/apiClient.js';
import { downloadText } from '../lib/downloads.js';
import { useAsync } from '../hooks/useAsync.js';

const modulesList = [{ id: 'overview', label: '销售概览' }, { id: 'region', label: '区域分析' }, { id: 'ranking', label: '产品排行' }, { id: 'anomaly', label: '异常指标' }, { id: 'forecast', label: '趋势预测' }];
const defaultModules = modulesList.map((module) => module.id);

export default function ReportView() {
  const [reportType, setReportType] = useState('月报');
  const [modules, setModules] = useState(defaultModules);
  const [request, setRequest] = useState(null);
  const report = useAsync((signal) => request ? apiClient.generateReport(request, { signal }) : Promise.resolve(null), [request]);
  const toggle = (id) => setModules((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const result = report.data?.data;

  return <section className="workspace">
    <div className="panel panel--span-4"><div className="panel-header"><h2>报告配置</h2><span>模板驱动</span></div><label className="field-label">报告类型<select value={reportType} onChange={(event) => setReportType(event.target.value)}><option>周报</option><option>月报</option><option>自定义报告</option></select></label><div className="check-list">{modulesList.map((module) => <label key={module.id}><input type="checkbox" checked={modules.includes(module.id)} onChange={() => toggle(module.id)} />{module.label}</label>)}</div><div className="actions-row"><button type="button" disabled={!modules.length || report.loading} onClick={() => setRequest({ report_type: reportType, modules })}>{report.loading ? '生成中...' : '生成报告'}</button><button type="button" disabled={!result} onClick={() => downloadText(`${result.period}-智能BI经营分析报告.md`, result.markdown, 'text/markdown;charset=utf-8')}>导出 Markdown</button></div></div>
    <div className="panel panel--span-8"><div className="panel-header"><h2>{result?.title || '报告预览'}</h2><span>{result ? `${result.engine === 'ai' ? 'AI 辅助' : '本地分析'} · ${result.period}` : '等待生成'}</span></div>{request ? <AsyncPanel resource={report} minHeight={420}>{(response) => <div className="report-preview">{(response?.data?.sections || []).map((section) => <article key={section.id}><h3>{section.title}</h3><p>{section.content}</p></article>)}</div>}</AsyncPanel> : <div className="empty-state report-placeholder">选择报告类型和模块后生成预览</div>}</div>
  </section>;
}
