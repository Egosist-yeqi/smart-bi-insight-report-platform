import React, { useState } from 'react';
import AsyncPanel from '../components/AsyncPanel.jsx';
import { apiClient } from '../lib/apiClient.js';
import { useAsync } from '../hooks/useAsync.js';

const emptyForm = {
  title: '', owner: '', priority: 'medium', due_date: '', target_metric: '', source_type: 'manual', evidence: '',
};

const sourceLabels = { manual: '手动创建', anomaly: '异常归因', forecast: '趋势预测', query: '智能查询', report: '经营报告' };
const priorityLabels = { high: '高优先级', medium: '中优先级', low: '低优先级' };
const statusLabels = { open: '待确认', in_progress: '执行中', completed: '已复盘' };

function suggestions(scenario) {
  const amount = scenario?.amount_label || '销售额';
  const region = scenario?.region_label || '区域';
  const entity = scenario?.entity_label || '产品';
  return [
    { title: `核查${region}${amount}异动的驱动因素`, priority: 'high', source_type: 'anomaly', target_metric: amount, evidence: `从“异常归因”核对${region}、${entity}和对象结构的变化证据。` },
    { title: `制定下月${amount}预测偏差应对方案`, priority: 'medium', source_type: 'forecast', target_metric: amount, evidence: '依据“趋势预测”中的历史趋势与预测值，明确可控杠杆和复核节点。' },
    { title: `复盘本期重点${entity}的经营表现`, priority: 'low', source_type: 'query', target_metric: amount, evidence: `通过“智能查询”补充${entity}排行、毛利和结构变化证据。` },
  ];
}

export default function ActionView({ scenario }) {
  const resource = useAsync((signal) => apiClient.actions({ signal }), []);
  const [form, setForm] = useState(emptyForm);
  const [reviewNotes, setReviewNotes] = useState({});
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const data = resource.data?.data;
  const items = data?.items || [];
  const summary = data?.summary || { open: 0, in_progress: 0, completed: 0, overdue: 0 };

  function updateForm(event) { setForm((current) => ({ ...current, [event.target.name]: event.target.value })); }
  function chooseSuggestion(item) { setForm({ ...emptyForm, ...item }); setMessage('已载入建议草案，请补充负责人和截止日期后创建。'); }
  async function createAction(event) {
    event.preventDefault();
    if (!form.title.trim()) return;
    setSaving(true); setMessage('');
    try {
      await apiClient.createAction({ ...form, title: form.title.trim(), owner: form.owner || null, due_date: form.due_date || null, target_metric: form.target_metric || null, evidence: form.evidence || null });
      setForm(emptyForm); setMessage('行动项已创建，等待负责人确认执行。'); resource.reload();
    } catch (error) { setMessage(error.message || '创建失败，请稍后重试。'); }
    finally { setSaving(false); }
  }
  async function updateAction(actionId, payload) {
    setSaving(true); setMessage('');
    try { await apiClient.updateAction(actionId, payload); setMessage('行动状态已更新。'); resource.reload(); }
    catch (error) { setMessage(error.message || '更新失败，请稍后重试。'); }
    finally { setSaving(false); }
  }

  return <section className="workspace">
    <div className="panel panel--span-12 action-intro">
      <div><p className="eyebrow">Decision loop</p><h2>行动中心</h2><p>把数据发现转成需要人工确认、执行和复盘的行动项。系统不会自动批准或关闭任何行动。</p></div>
      <div className="action-summary" aria-label="行动汇总"><span><strong>{summary.open}</strong>待确认</span><span><strong>{summary.in_progress}</strong>执行中</span><span><strong>{summary.completed}</strong>已复盘</span><span className={summary.overdue ? 'action-summary__overdue' : ''}><strong>{summary.overdue}</strong>已逾期</span></div>
    </div>
    <div className="panel panel--span-7">
      <div className="panel-header"><div><h2>创建行动项</h2><p>填写业务责任、目标和关联证据，形成可复盘的决策记录。</p></div></div>
      <form className="action-form" onSubmit={createAction}>
        <label className="field-label action-form__wide">行动内容<input name="title" value={form.title} onChange={updateForm} maxLength="180" placeholder="例如：核查华东区域经营金额下降原因" required /></label>
        <label className="field-label">负责人<input name="owner" value={form.owner} onChange={updateForm} maxLength="80" placeholder="例如：区域运营负责人" /></label>
        <label className="field-label">截止日期<input name="due_date" value={form.due_date} onChange={updateForm} type="date" /></label>
        <label className="field-label">优先级<select name="priority" value={form.priority} onChange={updateForm}>{Object.entries(priorityLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <label className="field-label">证据来源<select name="source_type" value={form.source_type} onChange={updateForm}>{Object.entries(sourceLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <label className="field-label action-form__wide">目标指标<input name="target_metric" value={form.target_metric} onChange={updateForm} maxLength="80" placeholder={scenario?.amount_label || '例如：销售额'} /></label>
        <label className="field-label action-form__wide">数据证据<textarea name="evidence" value={form.evidence} onChange={updateForm} maxLength="1200" placeholder="记录关联的异常、预测、查询或报告结论，便于后续核查。" /></label>
        <div className="actions-row action-form__wide"><button type="submit" disabled={saving || !form.title.trim()}>创建待确认行动</button>{message && <p className={message.includes('失败') ? 'form-status form-status--error' : 'form-status'}>{message}</p>}</div>
      </form>
    </div>
    <div className="panel panel--span-5">
      <div className="panel-header"><div><h2>建议草案</h2><p>随当前场景调整，仅供人工确认后转为行动。</p></div></div>
      <div className="action-suggestions">{suggestions(scenario).map((item) => <article key={item.title}><span className={`priority priority--${item.priority}`}>{priorityLabels[item.priority]}</span><strong>{item.title}</strong><small>{item.evidence}</small><button type="button" onClick={() => chooseSuggestion(item)}>载入草案</button></article>)}</div>
    </div>
    <div className="panel panel--span-12">
      <div className="panel-header"><div><h2>行动清单</h2><p>关闭行动前必须填写复盘结论，保证建议与实际效果可以区分。</p></div><span>{items.length} 项记录</span></div>
      <AsyncPanel resource={resource} minHeight={items.length ? 120 : 220}>{() => items.length ? <div className="action-list">{items.map((item) => <article className="action-item" key={item.id}>
        <div className="action-item__header"><div><span className={`priority priority--${item.priority}`}>{priorityLabels[item.priority]}</span><h3>{item.title}</h3></div><span className={`action-status action-status--${item.status}`}>{statusLabels[item.status]}</span></div>
        <dl><div><dt>负责人</dt><dd>{item.owner || '待指定'}</dd></div><div><dt>截止日</dt><dd>{item.due_date || '未设置'}</dd></div><div><dt>目标指标</dt><dd>{item.target_metric || '未设置'}</dd></div><div><dt>证据来源</dt><dd>{sourceLabels[item.source_type]}</dd></div></dl>
        {item.evidence && <p className="action-item__evidence"><strong>数据证据</strong>{item.evidence}</p>}
        {item.status !== 'completed' && <div className="action-item__controls">{item.status === 'open' && <button type="button" disabled={saving} onClick={() => updateAction(item.id, { status: 'in_progress' })}>标记为执行中</button>}<label>复盘结论<textarea value={reviewNotes[item.id] || ''} onChange={(event) => setReviewNotes((current) => ({ ...current, [item.id]: event.target.value }))} maxLength="1200" placeholder="说明实际结果、影响及下一步。" /></label><button type="button" className="button-secondary" disabled={saving} onClick={() => updateAction(item.id, { status: 'completed', review_notes: reviewNotes[item.id] || '' })}>完成并复盘</button></div>}
        {item.status === 'completed' && <p className="action-item__review"><strong>复盘结论</strong>{item.review_notes}</p>}
      </article>)}</div> : <div className="empty-state">尚无行动项。可从右侧建议草案开始，也可直接创建自定义行动。</div>}</AsyncPanel>
    </div>
  </section>;
}
