import React from 'react';

const navItems = ['智能查询', '仪表盘', '报告生成', '异常归因', '趋势预测', '系统配置'];

function statusText(healthResource, providerResource) {
  const health = healthResource.data?.data;
  const provider = providerResource.data?.data;
  if (healthResource.loading) {
    return { database: '服务检查中', analysis: '分析状态检查中', detail: '正在连接后端服务' };
  }
  if (healthResource.error) {
    return { database: '服务不可用', analysis: '健康检查失败', detail: healthResource.error.message || '无法连接到后端服务' };
  }
  if (!health) {
    return { database: '服务不可用', analysis: '健康状态未知', detail: '未收到健康检查响应' };
  }
  const database = health.database === 'up' ? 'MySQL 正常' : 'MySQL 异常';
  const analysis = providerResource.error
    ? '分析服务不可用'
    : providerResource.loading
      ? '分析状态检查中'
      : provider?.configured && provider.enabled
    ? provider.provider_name
    : '本地分析';
  return { database, analysis, detail: `${health.seeded_orders} 条销售订单` };
}

export default function AppShell({ active, setActive, question, setQuestion, onRun, healthResource, onRefreshStatus, providerResource, children }) {
  const status = statusText(healthResource, providerResource);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark">BI</span>
          <div><strong>智能 BI</strong><small>数据洞察平台</small></div>
        </div>
        <nav className="nav-list" aria-label="功能导航">
          {navItems.map((item) => (
            <button className={active === item ? 'nav-item nav-item--active' : 'nav-item'} key={item} onClick={() => setActive(item)} type="button">{item}</button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span>{status.database}</span>
          <strong>{status.analysis}</strong>
          <small>{status.detail}</small>
        </div>
      </aside>
      <main className="main-panel">
        <header className="topbar">
          <div>
            <h1>智能 BI 数据洞察与报告生成平台</h1>
            <p>自然语言查询、Text-to-SQL、异常归因、预测和报告输出的一体化原型。</p>
            <button className="status-refresh" type="button" onClick={onRefreshStatus} disabled={healthResource.loading}>{healthResource.error ? '重试状态检查' : '刷新状态'}</button>
          </div>
          <form className="command-bar" onSubmit={(event) => { event.preventDefault(); onRun(); }}>
            <input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="输入经营分析问题" />
            <button type="submit">运行查询</button>
          </form>
        </header>
        {children}
      </main>
    </div>
  );
}
