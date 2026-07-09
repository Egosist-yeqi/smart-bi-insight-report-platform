import { latestMonth, previousMonth } from '../data/sampleData.js';

export function sum(records, key) {
  return records.reduce((total, record) => total + Number(record[key] || 0), 0);
}

export function groupBy(records, key) {
  return records.reduce((groups, record) => {
    const groupKey = record[key];
    groups[groupKey] = groups[groupKey] || [];
    groups[groupKey].push(record);
    return groups;
  }, {});
}

export function filterRecords(records, filters = {}) {
  return records.filter((record) => {
    const monthMatch = !filters.month || record.month === filters.month;
    const regionMatch = !filters.region || filters.region === '全部' || record.region === filters.region;
    const categoryMatch = !filters.category || filters.category === '全部' || record.category === filters.category;
    const customerMatch = !filters.customerType || filters.customerType === '全部' || record.customerType === filters.customerType;
    return monthMatch && regionMatch && categoryMatch && customerMatch;
  });
}

export function getKpis(records) {
  const amount = sum(records, 'amount');
  const quantity = sum(records, 'quantity');
  const profit = sum(records, 'profit');
  const orderCount = records.length;

  return {
    amount,
    quantity,
    orderCount,
    avgOrderValue: orderCount ? amount / orderCount : 0,
    profitRate: amount ? profit / amount : 0,
  };
}

export function getKpiDeltas(records) {
  const current = getKpis(records.filter((record) => record.month === latestMonth));
  const previous = getKpis(records.filter((record) => record.month === previousMonth));
  return {
    amount: previous.amount ? (current.amount - previous.amount) / previous.amount : 0,
    quantity: previous.quantity ? (current.quantity - previous.quantity) / previous.quantity : 0,
    avgOrderValue: previous.avgOrderValue ? (current.avgOrderValue - previous.avgOrderValue) / previous.avgOrderValue : 0,
    profitRate: previous.profitRate ? current.profitRate - previous.profitRate : 0,
  };
}

export function rankingBy(records, groupKey, metric = 'amount') {
  return Object.entries(groupBy(records, groupKey))
    .map(([name, items]) => ({
      name,
      amount: sum(items, 'amount'),
      quantity: sum(items, 'quantity'),
      profit: sum(items, 'profit'),
      orderCount: items.length,
      profitRate: sum(items, 'amount') ? sum(items, 'profit') / sum(items, 'amount') : 0,
    }))
    .sort((a, b) => b[metric] - a[metric]);
}

export function monthlyTrend(records) {
  return rankingBy(records, 'month', 'amount').sort((a, b) => a.name.localeCompare(b.name));
}

export function weeklyTrend(records) {
  return rankingBy(records, 'week', 'amount').sort((a, b) => a.name.localeCompare(b.name));
}

export function getTopProduct(records, filters) {
  return rankingBy(filterRecords(records, filters), 'productName', 'amount')[0];
}

export function getRegionComparison(records) {
  const current = rankingBy(records.filter((record) => record.month === latestMonth), 'region', 'amount');
  const previous = rankingBy(records.filter((record) => record.month === previousMonth), 'region', 'amount');
  const previousMap = new Map(previous.map((item) => [item.name, item.amount]));
  return current.map((item) => {
    const baseline = previousMap.get(item.name) || 0;
    return {
      ...item,
      previousAmount: baseline,
      delta: baseline ? (item.amount - baseline) / baseline : 0,
    };
  });
}

export function detectAnomalies(records) {
  const regionComparison = getRegionComparison(records);
  return regionComparison
    .filter((item) => Math.abs(item.delta) >= 0.18)
    .map((item) => ({
      region: item.name,
      metric: '销售额',
      currentAmount: item.amount,
      previousAmount: item.previousAmount,
      delta: item.delta,
      level: item.delta < 0 ? '下降预警' : '增长提醒',
      reason: item.delta < 0
        ? `${item.name} 最新月销售额较上月下降，主要需要检查渠道客户订单和重点产品出货节奏。`
        : `${item.name} 最新月销售额明显增长，可继续拆解高贡献产品和客户类型。`,
    }));
}

export function forecastNextMonth(records) {
  const trend = monthlyTrend(records);
  const values = trend.map((item) => item.amount);
  const last = values.at(-1) || 0;
  const previous = values.at(-2) || last;
  const averageGrowth = previous ? (last - previous) / previous : 0;
  const conservativeGrowth = Math.max(Math.min(averageGrowth * 0.65, 0.18), -0.12);
  return {
    label: '2026-07',
    predictedAmount: Math.round(last * (1 + conservativeGrowth)),
    growth: conservativeGrowth,
    basis: `基于 ${trend.map((item) => item.name).join('、')} 的月度销售额变化进行线性外推，并对增长幅度做保守收敛。`,
  };
}

export function runScenario(records, { region = '华东', promoIncrease = 0.1, priceDrop = 0.05 } = {}) {
  const latest = filterRecords(records, { month: latestMonth, region });
  const base = sum(latest, 'amount');
  const promoLift = promoIncrease * 0.42;
  const priceImpact = -priceDrop * 0.68;
  const netChange = promoLift + priceImpact;
  return {
    region,
    base,
    netChange,
    simulatedAmount: Math.round(base * (1 + netChange)),
    explanation: `${region} 最新月销售额为 ${Math.round(base)}。在促销投入增加 ${(promoIncrease * 100).toFixed(0)}%、价格下降 ${(priceDrop * 100).toFixed(0)}% 的假设下，模型按演示弹性估算净影响为 ${(netChange * 100).toFixed(1)}%。`,
  };
}

export function toCsv(rows) {
  if (!rows.length) return '';
  const headers = Object.keys(rows[0]);
  const body = rows.map((row) => headers.map((header) => JSON.stringify(row[header] ?? '')).join(','));
  return [headers.join(','), ...body].join('\n');
}
