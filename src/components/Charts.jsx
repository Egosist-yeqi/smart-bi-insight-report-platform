import { formatCurrency, formatNumber, formatPercent } from '../lib/formatters.js';
import React from 'react';

function maxValue(data, key) {
  return Math.max(...data.map((item) => Number(item[key]) || 0), 1);
}

function rankingProfitRate(row) {
  const provided = Number(row.profit_rate);
  if (Number.isFinite(provided)) return provided;

  const amount = Number(row.amount);
  const profit = Number(row.profit);
  return Number.isFinite(profit) && Number.isFinite(amount) && amount !== 0
    ? profit / amount
    : 0;
}

function tickVisibility(index, count) {
  if (count <= 6) return { desktop: true, mobile: true };

  const last = count - 1;
  const desktopStep = count >= 16 ? 3 : 2;
  const mobileStep = count >= 16 ? 6 : 3;
  const edge = index === 0 || index === last;
  return {
    desktop: edge || index % desktopStep === 0,
    mobile: edge || index % mobileStep === 0,
  };
}

export function BarChart({ data, valueKey = 'amount', label = '销售额', formatter = formatCurrency }) {
  const max = maxValue(data, valueKey);

  return (
    <div className="bar-chart" aria-label={label}>
      {data.map((item) => (
        <div className="bar-row" key={item.name}>
          <span>{item.name}</span>
          <div className="bar-row__track">
            <div className="bar-row__fill" style={{ width: `${Math.max(((Number(item[valueKey]) || 0) / max) * 100, 4)}%` }} />
          </div>
          <strong>{formatter(item[valueKey])}</strong>
        </div>
      ))}
    </div>
  );
}

export function LineChart({ data, valueKey = 'amount', label = '趋势' }) {
  const width = 560;
  const height = 180;
  const pad = 42;
  const max = maxValue(data, valueKey);
  const points = data.map((item, index) => {
    const x = pad + (index * (width - pad * 2)) / Math.max(data.length - 1, 1);
    const y = height - pad - ((Number(item[valueKey]) || 0) / max) * (height - pad * 2);
    return { ...item, x, y };
  });
  const path = points.map((point) => `${point.x},${point.y}`).join(' ');

  return (
    <div className="line-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
        <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} className="chart-axis" />
        <polyline points={path} className="chart-line" />
        {points.map((point, index) => {
          const ticks = tickVisibility(index, points.length);
          return <g key={point.name}>
            <circle cx={point.x} cy={point.y} r="4" className="chart-point" />
            {ticks.desktop && <text x={point.x} y={height - 4} textAnchor="middle" className={ticks.mobile ? 'chart-label' : 'chart-label chart-label--desktop-only'}>{point.name}</text>}
          </g>;
        })}
      </svg>
    </div>
  );
}

export function ContributionGrid({ rows }) {
  return (
    <div className="contribution-grid">
      {rows.map((row) => (
        <article key={row.name} className="contribution-item">
          <div>
            <span>{row.name}</span>
            <strong>{formatCurrency(row.amount)}</strong>
          </div>
          <small>毛利率 {formatPercent(rankingProfitRate(row))} · 数量 {formatNumber(row.quantity)}</small>
        </article>
      ))}
    </div>
  );
}
