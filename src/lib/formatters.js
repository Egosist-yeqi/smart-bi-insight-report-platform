function finiteNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatCurrency(value) {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    maximumFractionDigits: 0,
  }).format(finiteNumber(value));
}

export function formatNumber(value) {
  return new Intl.NumberFormat('zh-CN', {
    maximumFractionDigits: 0,
  }).format(finiteNumber(value));
}

export function formatPercent(value) {
  return `${(finiteNumber(value) * 100).toFixed(1)}%`;
}

export function formatDelta(value) {
  const normalized = finiteNumber(value);
  const sign = normalized > 0 ? '+' : '';
  return `${sign}${(normalized * 100).toFixed(1)}%`;
}
