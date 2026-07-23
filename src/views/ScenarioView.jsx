import React, { useMemo, useState } from 'react';
import AsyncPanel from '../components/AsyncPanel.jsx';
import DataTable from '../components/DataTable.jsx';
import { downloadText } from '../lib/downloads.js';
import { apiClient } from '../lib/apiClient.js';
import { useAsync } from '../hooks/useAsync.js';

const standardFields = [
  ['record_id', '业务记录唯一编号'], ['date', '业务日期，格式 YYYY-MM-DD'],
  ['region', '组织、院区、网点或业务区域'], ['province', '城市或省份'],
  ['item_id', '项目/产品数字编号'], ['item_name', '项目、产品或服务名称'],
  ['category', '科室、业务线或品类'], ['customer_type', '客户、患者或用户类型'],
  ['quantity', '数量、人次、笔数或席位'], ['amount', '收入、GMV、产值或交易额'], ['profit', '收益或贡献金额'],
];

function csvValue(value) {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function templateCsv(scenario) {
  return [scenario.csv_headers.join(','), scenario.csv_headers.map((key) => csvValue(scenario.sample_row[key])).join(',')].join('\n');
}

export default function ScenarioView({ onScenarioChange }) {
  const resource = useAsync((signal) => apiClient.scenarios({ signal }), []);
  const [selectedId, setSelectedId] = useState('');
  const [file, setFile] = useState(null);
  const [mutation, setMutation] = useState(null);
  const data = resource.data?.data;
  const active = data?.scenarios?.find((item) => item.active) || data?.scenarios?.[0];
  const selected = data?.scenarios?.find((item) => item.id === selectedId) || active;
  const loading = Boolean(mutation?.loading);

  const fieldRows = useMemo(() => standardFields.map(([field, description]) => ({ field, description })), []);

  async function activate(scenario) {
    setMutation({ loading: true, error: null, message: null });
    try {
      const result = await apiClient.activateScenario(scenario.id);
      setSelectedId(scenario.id);
      setFile(null);
      setMutation({ loading: false, error: null, message: `已加载 ${result.data.scenario.title} 演示数据（${result.data.orders_loaded} 条）。` });
      resource.reload();
      onScenarioChange?.();
    } catch (error) {
      setMutation({ loading: false, error, message: null });
    }
  }

  async function importCsv() {
    if (!selected || !file) return;
    setMutation({ loading: true, error: null, message: null });
    try {
      const csvText = await file.text();
      const result = await apiClient.importScenario({ scenario_id: selected.id, csv_text: csvText });
      setMutation({ loading: false, error: null, message: `已导入 ${result.data.rows_imported} 条 ${selected.title} 数据。` });
      resource.reload();
      onScenarioChange?.();
    } catch (error) {
      setMutation({ loading: false, error, message: null });
    }
  }

  return <section className="workspace"><AsyncPanel resource={resource} minHeight={620}>{() => <>
    <div className="panel panel--span-12">
      <div className="panel-header"><div><h2>行业场景库</h2><p>选择一个场景即可装载演示数据和行业问题；切换或导入会替换当前数据集与查询历史。</p></div><span>{data?.data_source === 'imported' ? '自有数据' : '演示数据'}</span></div>
      <div className="scenario-grid">{(data?.scenarios || []).map((scenario) => <article className={`scenario-item ${scenario.active ? 'scenario-item--active' : ''}`} key={scenario.id}><div><h3>{scenario.title}</h3><span>{scenario.active ? '当前场景' : scenario.amount_label}</span></div><p>{scenario.description}</p><small>{scenario.entity_label} · {scenario.quantity_label} · {scenario.amount_label}</small><button type="button" disabled={loading || scenario.active} onClick={() => activate(scenario)}>{scenario.active ? '正在使用' : '加载演示数据'}</button></article>)}</div>
    </div>
    <div className="panel panel--span-7">
      <div className="panel-header"><div><h2>导入自有数据</h2><p>先选行业模板，再下载 CSV 模板并按固定字段上传。</p></div><span>{selected?.title || '未选择'}</span></div>
      <div className="scenario-import-controls"><label className="field-label">行业模板<select value={selected?.id || ''} disabled={loading} onChange={(event) => setSelectedId(event.target.value)}>{(data?.scenarios || []).map((scenario) => <option key={scenario.id} value={scenario.id}>{scenario.title}</option>)}</select></label><label className="field-label">CSV 数据文件<input type="file" accept=".csv,text/csv" disabled={loading} onChange={(event) => setFile(event.target.files?.[0] || null)} /></label></div>
      <div className="actions-row"><button type="button" disabled={!selected || loading} onClick={() => downloadText(`${selected.id}-template.csv`, templateCsv(selected), 'text/csv;charset=utf-8')}>下载 CSV 模板</button><button type="button" disabled={!file || loading} onClick={importCsv}>导入并替换当前数据</button></div>
      {mutation?.message && <p className="form-status">{mutation.message}</p>}{mutation?.error && <p className="form-status form-status--error">{mutation.error.message}</p>}
      {selected && <div className="scenario-questions"><h3>{selected.title} 示例问题</h3>{selected.question_groups.map((group) => <div key={group.title}><strong>{group.title}</strong><p>{group.questions.join('；')}</p></div>)}</div>}
    </div>
    <div className="panel panel--span-5">
      <div className="panel-header"><div><h2>模板字段边界</h2><p>导入后系统仅在这些受控字段上进行指标、趋势、归因和预测分析。</p></div><span>11 列</span></div>
      <DataTable rows={fieldRows} />
      {selected && <div className="scenario-mapping"><strong>{selected.title} 语义映射</strong>{selected.field_mappings.map((mapping) => <span key={mapping.field}>{mapping.field}：{mapping.label}</span>)}</div>}
    </div>
  </>}</AsyncPanel></section>;
}
