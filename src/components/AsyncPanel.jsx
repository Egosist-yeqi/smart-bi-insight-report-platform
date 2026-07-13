import React from 'react';

export default function AsyncPanel({ resource, children, minHeight = 260 }) {
  if (resource.loading) {
    return <div className="async-panel" style={{ minHeight }} role="status">正在加载数据...</div>;
  }

  if (resource.error) {
    return (
      <div className="async-panel async-panel--error" style={{ minHeight }} role="alert">
        <strong>{resource.error.message || '加载失败'}</strong>
        <button type="button" onClick={resource.reload}>重试</button>
      </div>
    );
  }

  return children(resource.data);
}
