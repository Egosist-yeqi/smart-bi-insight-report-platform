import { formatCurrency, formatDelta, formatNumber, formatPercent } from '../lib/formatters.js';
import React from 'react';

const formatters = {
  currency: formatCurrency,
  number: formatNumber,
  percent: formatPercent,
};

export default function MetricCard({ label, value, delta, type = 'number', note }) {
  const formatter = formatters[type] || formatNumber;
  const positive = delta >= 0;

  return (
    <section className="metric-card">
      <div className="metric-card__label">{label}</div>
      <strong>{formatter(value)}</strong>
      <div className="metric-card__meta">
        <span className={positive ? 'delta delta--up' : 'delta delta--down'}>{formatDelta(delta)}</span>
        <span>{note}</span>
      </div>
    </section>
  );
}
