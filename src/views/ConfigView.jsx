import React, { useEffect, useState } from 'react';
import AsyncPanel from '../components/AsyncPanel.jsx';
import DataTable from '../components/DataTable.jsx';
import { apiClient } from '../lib/apiClient.js';
import { useAsync } from '../hooks/useAsync.js';

const blankForm = { provider_name: 'OpenAI Compatible', base_url: '', api_key: '', model: '', timeout_seconds: 30, enabled: true, allow_private_network: false };

function formFromSettings(settings) {
  if (!settings?.configured) return blankForm;
  return { provider_name: settings.provider_name || '', base_url: settings.base_url || '', api_key: '', model: settings.model || '', timeout_seconds: settings.timeout_seconds || 30, enabled: Boolean(settings.enabled), allow_private_network: Boolean(settings.allow_private_network) };
}

function ActionState({ action, label }) {
  if (!action) return null;
  return <p className={action.error ? 'form-status form-status--error' : 'form-status'}>{action.loading ? `${label}中...` : action.error ? action.error.message : action.success ? `${label}成功` : ''}</p>;
}

export default function ConfigView({ onProviderChange }) {
  const resource = useAsync(async (signal) => Promise.all([apiClient.metadata({ signal }), apiClient.getAi({ signal }), apiClient.health({ signal })]), []);
  const [form, setForm] = useState(blankForm);
  const [save, setSave] = useState(null);
  const [test, setTest] = useState(null);
  const [remove, setRemove] = useState(null);
  const settings = resource.data?.[1]?.data;

  useEffect(() => { if (settings) setForm(formFromSettings(settings)); }, [settings?.configured, settings?.provider_name, settings?.base_url, settings?.model, settings?.timeout_seconds, settings?.enabled, settings?.allow_private_network]);
  const setValue = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const payload = () => ({ ...form, api_key: form.api_key || undefined });
  const run = async (setter, call, label) => { setter({ loading: true, error: null, success: false }); try { const result = await call(); setter({ loading: false, error: null, success: true, result }); return result; } catch (error) { setter({ loading: false, error, success: false }); return null; } };
  const saveSettings = async () => { const result = await run(setSave, () => apiClient.saveAi(payload()), '保存'); if (result) { setForm((current) => ({ ...current, api_key: '' })); resource.reload(); onProviderChange?.(); } };
  const testSettings = () => run(setTest, () => form.api_key ? apiClient.testAi(payload()) : apiClient.testAi({}), '连接测试');
  const deleteSettings = async () => { const result = await run(setRemove, () => apiClient.deleteAi(), '删除'); if (result) { setForm(blankForm); resource.reload(); onProviderChange?.(); } };

  return <section className="workspace"><AsyncPanel resource={resource} minHeight={620}>{(responses) => { const metadata = responses?.[0]?.data; const health = responses?.[2]?.data; return <><div className="panel panel--span-7"><div className="panel-header"><h2>指标字典</h2><span>{metadata?.metrics?.length || 0} 项</span></div><DataTable rows={(metadata?.metrics || []).map((metric) => ({ name: metric.metric_name, code: metric.metric_code, formula: metric.formula, description: metric.description }))} /></div><div className="panel panel--span-5"><div className="panel-header"><h2>数据源状态</h2><span>{health?.database === 'up' ? 'MySQL 正常' : '连接异常'}</span></div><div className="source-box"><strong>sales_order</strong><span>{health?.seeded_orders || 0} 条销售订单</span><small>字段覆盖订单日期、区域、产品、客户类型、销售数量、销售额和毛利。</small></div></div><div className="panel panel--span-12"><div className="panel-header"><div><h2>AI 服务配置</h2><p>密钥仅用于本次保存或连接测试，保存后不会再次显示。</p></div><span>{settings?.configured ? settings.api_key_hint : '本地分析'}</span></div><div className="config-grid"><label className="field-label">服务名称<input value={form.provider_name} onChange={(event) => setValue('provider_name', event.target.value)} /></label><label className="field-label">Base URL<input type="url" value={form.base_url} placeholder="https://api.example.com/v1" onChange={(event) => setValue('base_url', event.target.value)} /></label><label className="field-label">模型<input value={form.model} onChange={(event) => setValue('model', event.target.value)} /></label><label className="field-label">超时秒数<input type="number" min="1" max="120" value={form.timeout_seconds} onChange={(event) => setValue('timeout_seconds', Number(event.target.value))} /></label><label className="field-label">API 密钥<input type="password" autoComplete="new-password" value={form.api_key} placeholder={settings?.configured ? `已保存：${settings.api_key_hint}` : '首次保存必填'} onChange={(event) => setValue('api_key', event.target.value)} /></label></div><div className="check-list config-checks"><label><input type="checkbox" checked={form.enabled} onChange={(event) => setValue('enabled', event.target.checked)} />启用该 AI 服务</label><label><input type="checkbox" checked={form.allow_private_network} onChange={(event) => setValue('allow_private_network', event.target.checked)} />允许访问私有网络地址</label><p className="private-network-warning">仅在可信内部服务场景启用。允许私有网络可能扩大服务端请求范围。</p></div><div className="actions-row"><button type="button" disabled={save?.loading} onClick={saveSettings}>{save?.loading ? '保存中...' : '保存配置'}</button><button type="button" disabled={test?.loading} onClick={testSettings}>{test?.loading ? '测试中...' : '连接测试'}</button><button type="button" className="button-danger" disabled={!settings?.configured || remove?.loading} onClick={deleteSettings}>{remove?.loading ? '删除中...' : '删除配置'}</button></div><ActionState action={save} label="保存" /><ActionState action={test} label="连接测试" /><ActionState action={remove} label="删除" />{test?.success && <p className="form-status">已连接 {test.result.data.provider} / {test.result.data.model}，耗时 {test.result.data.latency_ms} ms。</p>}</div></>; }}</AsyncPanel></section>;
}
