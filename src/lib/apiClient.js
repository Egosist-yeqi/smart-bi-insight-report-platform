export class ApiError extends Error {
  constructor(code, message, requestId, details) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

function toQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '' && value !== '全部') {
      query.set(key, value);
    }
  });
  const text = query.toString();
  return text ? `?${text}` : '';
}

export function createApiClient(fetchImpl = globalThis.fetch) {
  async function request(path, { method = 'GET', body, signal } = {}) {
    const headers = { Accept: 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';

    let response;
    try {
      response = await fetchImpl(path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal,
      });
    } catch (error) {
      if (error?.name === 'AbortError') throw error;
      throw new ApiError('NETWORK_ERROR', '无法连接到后端服务。');
    }

    let envelope = {};
    try {
      const text = await response.text();
      envelope = text ? JSON.parse(text) : {};
    } catch {
      envelope = {};
    }

    if (!response.ok) {
      const error = envelope.error || {};
      throw new ApiError(
        error.code || 'REQUEST_FAILED',
        error.message || '请求失败，请稍后重试。',
        envelope.request_id,
        error.details,
      );
    }

    return { data: envelope.data, requestId: envelope.request_id };
  }

  return {
    health: (options) => request('/api/health', options),
    metadata: (options) => request('/api/metadata', options),
    dashboard: (filters = {}, options) => request(`/api/dashboard${toQuery({
      region: filters.region,
      category: filters.category,
      customer_type: filters.customerType,
    })}`, options),
    query: (question, options) => request('/api/query', { ...options, method: 'POST', body: { question } }),
    anomalies: (options) => request('/api/anomalies', options),
    forecast: (options) => request('/api/forecast', options),
    scenarios: (options) => request('/api/scenarios', options),
    activateScenario: (scenarioId, options) => request(`/api/scenarios/${encodeURIComponent(scenarioId)}/activate`, { ...options, method: 'POST' }),
    previewScenarioImport: (payload, options) => request('/api/scenarios/import/preview', { ...options, method: 'POST', body: payload }),
    importScenario: (payload, options) => request('/api/scenarios/import', { ...options, method: 'POST', body: payload }),
    generateReport: (payload, options) => request('/api/reports/generate', { ...options, method: 'POST', body: payload }),
    getAi: (options) => request('/api/settings/ai', options),
    saveAi: (payload, options) => request('/api/settings/ai', { ...options, method: 'PUT', body: payload }),
    testAi: (payload, options) => request('/api/settings/ai/test', { ...options, method: 'POST', body: payload }),
    deleteAi: (options) => request('/api/settings/ai', { ...options, method: 'DELETE' }),
    queryHistory: (options) => request('/api/query-history?limit=20', options),
  };
}

export const apiClient = createApiClient();
