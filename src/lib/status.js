export function statusText(healthResource, providerResource) {
  const health = healthResource.data?.data;
  const provider = providerResource.data?.data;
  if (healthResource.loading) {
    return { database: '服务检查中', analysis: '分析状态检查中', detail: '正在连接后端服务' };
  }
  if (healthResource.error) {
    if (
      healthResource.error.code === 'DATABASE_UNAVAILABLE'
      || healthResource.error.details?.database === 'down'
    ) {
      return {
        database: 'MySQL 异常',
        analysis: '分析服务受限',
        detail: healthResource.error.message || '数据库连接不可用。',
      };
    }
    return { database: '服务不可用', analysis: '健康检查失败', detail: healthResource.error.message || '无法连接到后端服务' };
  }
  if (!health) {
    return { database: '服务不可用', analysis: '健康状态未知', detail: '未收到健康检查响应' };
  }

  const database = health.database === 'up' ? 'MySQL 正常' : 'MySQL 异常';
  const healthAnalysis = health.ai_mode === 'ai' ? (health.provider || 'AI 分析') : '本地分析';
  const analysis = providerResource.loading
    ? '分析状态检查中'
    : provider?.configured && provider.enabled
      ? provider.provider_name
      : providerResource.error
        ? healthAnalysis
        : '本地分析';
  return { database, analysis, detail: `${health.seeded_orders} 条销售订单` };
}
