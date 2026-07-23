import React from 'react';
import { statusText } from '../lib/status.js';

const navItems = ['场景库', '智能查询', '仪表盘', '报告生成', '异常归因', '趋势预测', '系统配置'];

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
