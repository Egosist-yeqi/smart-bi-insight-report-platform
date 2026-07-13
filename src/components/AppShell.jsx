import React from 'react';

const navItems = ['智能查询', '仪表盘', '报告生成', '异常归因', '趋势预测', '系统配置'];

function statusText(health, provider) {
  if (!health) return { database: '服务检查中', analysis: '分析状态检查中' };
  const database = health.database === 'up' ? 'MySQL 正常' : 'MySQL 异常';
  const analysis = provider?.configured && provider.enabled
    ? provider.provider_name
    : '本地分析';
  return { database, analysis };
}

export default function AppShell({ active, setActive, question, setQuestion, onRun, healthResource, onRefreshStatus, provider, children }) {
  const health = healthResource.data?.data;
  const status = statusText(health, provider);

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
          <small>{health ? `${health.seeded_orders} 条销售订单` : '正在连接后端'}</small>
        </div>
      </aside>
      <main className="main-panel">
        <header className="topbar">
          <div>
            <h1>智能 BI 数据洞察与报告生成平台</h1>
            <p>自然语言查询、Text-to-SQL、异常归因、预测和报告输出的一体化原型。</p>
            <button className="status-refresh" type="button" onClick={onRefreshStatus} disabled={healthResource.loading}>刷新状态</button>
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
