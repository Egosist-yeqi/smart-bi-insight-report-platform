import React, { useEffect, useRef, useState } from 'react';
import AsyncPanel from '../components/AsyncPanel.jsx';
import DataTable from '../components/DataTable.jsx';
import { apiClient } from '../lib/apiClient.js';
import { useAsync } from '../hooks/useAsync.js';

const blankForm = {
  provider_name: 'OpenAI Compatible',
  base_url: '',
  api_key: '',
  model: '',
  timeout_seconds: 30,
  enabled: true,
  allow_private_network: false,
};

const actionLabels = { save: '保存', test: '连接测试', delete: '删除' };

function formFromSettings(settings) {
  if (!settings?.configured) return blankForm;
  return {
    provider_name: settings.provider_name || '',
    base_url: settings.base_url || '',
    api_key: '',
    model: settings.model || '',
    timeout_seconds: settings.timeout_seconds || 30,
    enabled: Boolean(settings.enabled),
    allow_private_network: Boolean(settings.allow_private_network),
  };
}

function MutationStatus({ mutation }) {
  if (!mutation) return null;
  const label = actionLabels[mutation.kind];
  if (mutation.loading) return <p className="form-status">{label}中...</p>;
  if (mutation.error) return <p className="form-status form-status--error">{mutation.error.message}</p>;
  if (mutation.kind === 'test') {
    return <p className="form-status">已连接 {mutation.result.data.provider} / {mutation.result.data.model}，耗时 {mutation.result.data.latency_ms} ms。</p>;
  }
  return <p className="form-status">{label}成功</p>;
}

export default function ConfigView({ onProviderChange }) {
  const resource = useAsync(
    (signal) => Promise.all([
      apiClient.metadata({ signal }),
      apiClient.getAi({ signal }),
      apiClient.health({ signal }),
    ]),
    [],
  );
  const [form, setForm] = useState(blankForm);
  const [mutation, setMutation] = useState(null);
  const mutationLock = useRef(false);
  const settings = resource.data?.[1]?.data;
  const mutationInFlight = Boolean(mutation?.loading);

  useEffect(() => {
    if (settings) setForm(formFromSettings(settings));
  }, [
    settings?.configured,
    settings?.provider_name,
    settings?.base_url,
    settings?.model,
    settings?.timeout_seconds,
    settings?.enabled,
    settings?.allow_private_network,
  ]);

  function setValue(key, value) {
    if (mutationInFlight) return;
    setMutation(null);
    setForm((current) => ({ ...current, [key]: value }));
  }

  function payload() {
    return { ...form, api_key: form.api_key || undefined };
  }

  async function runMutation(kind, request, onSuccess) {
    if (mutationLock.current) return;
    mutationLock.current = true;
    setMutation({ kind, loading: true, error: null, result: null });
    try {
      const result = await request();
      setMutation({ kind, loading: false, error: null, result });
      onSuccess?.(result);
    } catch (error) {
      setMutation({ kind, loading: false, error, result: null });
    } finally {
      mutationLock.current = false;
    }
  }

  function saveSettings() {
    const nextPayload = payload();
    runMutation('save', () => apiClient.saveAi(nextPayload), () => {
      setForm((current) => ({ ...current, api_key: '' }));
      resource.reload();
      onProviderChange?.();
    });
  }

  function testSettings() {
    const nextPayload = form.api_key ? payload() : {};
    runMutation('test', () => apiClient.testAi(nextPayload));
  }

  function deleteSettings() {
    runMutation('delete', () => apiClient.deleteAi(), () => {
      setForm(blankForm);
      resource.reload();
      onProviderChange?.();
    });
  }

  return (
    <section className="workspace">
      <AsyncPanel resource={resource} minHeight={620}>{(responses) => {
        const metadata = responses?.[0]?.data;
        const health = responses?.[2]?.data;
        return <>
          <div className="panel panel--span-7">
            <div className="panel-header"><h2>指标字典</h2><span>{metadata?.metrics?.length || 0} 项</span></div>
            <DataTable rows={(metadata?.metrics || []).map((metric) => ({ name: metric.metric_name, code: metric.metric_code, formula: metric.formula, description: metric.description }))} />
          </div>
          <div className="panel panel--span-5">
            <div className="panel-header"><h2>数据源状态</h2><span>{health?.database === 'up' ? 'MySQL 正常' : '连接异常'}</span></div>
            <div className="source-box"><strong>sales_order</strong><span>{health?.seeded_orders || 0} 条销售订单</span><small>字段覆盖订单日期、区域、产品、客户类型、销售数量、销售额和毛利。</small></div>
          </div>
          <div className="panel panel--span-12">
            <div className="panel-header"><div><h2>AI 服务配置</h2><p>密钥仅用于本次保存或连接测试，保存后不会再次显示。</p></div><span>{settings?.configured ? settings.api_key_hint : '本地分析'}</span></div>
            <div className="config-grid">
              <label className="field-label">服务名称<input disabled={mutationInFlight} value={form.provider_name} onChange={(event) => setValue('provider_name', event.target.value)} /></label>
              <label className="field-label">Base URL<input disabled={mutationInFlight} type="url" value={form.base_url} placeholder="https://api.example.com/v1" onChange={(event) => setValue('base_url', event.target.value)} /></label>
              <label className="field-label">模型<input disabled={mutationInFlight} value={form.model} onChange={(event) => setValue('model', event.target.value)} /></label>
              <label className="field-label">超时秒数<input disabled={mutationInFlight} type="number" min="1" max="120" value={form.timeout_seconds} onChange={(event) => setValue('timeout_seconds', Number(event.target.value))} /></label>
              <label className="field-label">API 密钥<input disabled={mutationInFlight} type="password" autoComplete="new-password" value={form.api_key} placeholder={settings?.configured ? `已保存：${settings.api_key_hint}` : '首次保存必填'} onChange={(event) => setValue('api_key', event.target.value)} /></label>
            </div>
            <div className="check-list config-checks">
              <label><input disabled={mutationInFlight} type="checkbox" checked={form.enabled} onChange={(event) => setValue('enabled', event.target.checked)} />启用该 AI 服务</label>
              <label><input disabled={mutationInFlight} type="checkbox" checked={form.allow_private_network} onChange={(event) => setValue('allow_private_network', event.target.checked)} />允许访问私有网络地址</label>
              <p className="private-network-warning">仅在可信内部服务场景启用。允许私有网络可能扩大服务端请求范围。</p>
            </div>
            <div className="actions-row">
              <button type="button" disabled={mutationInFlight} onClick={saveSettings}>保存配置</button>
              <button type="button" disabled={mutationInFlight} onClick={testSettings}>连接测试</button>
              <button type="button" className="button-danger" disabled={mutationInFlight || !settings?.configured} onClick={deleteSettings}>删除配置</button>
            </div>
            <MutationStatus mutation={mutation} />
          </div>
        </>;
      }}</AsyncPanel>
    </section>
  );
}
