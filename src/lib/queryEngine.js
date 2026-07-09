import {
  detectAnomalies,
  filterRecords,
  forecastNextMonth,
  getKpis,
  getRegionComparison,
  getTopProduct,
  rankingBy,
  runScenario,
  weeklyTrend,
} from './analytics.js';
import { latestMonth, previousMonth } from '../data/sampleData.js';

const dangerousSql = /\b(delete|update|insert|drop|alter|truncate|create|grant|revoke|merge|replace)\b/i;

export function isReadOnlySql(sql) {
  return /^\s*select\b/i.test(sql) && !dangerousSql.test(sql);
}

function buildResult({ intent, sql, explanation, rows, chartType = 'bar', summary, confidence = 0.86 }) {
  return {
    intent,
    sql,
    explanation,
    rows,
    chartType,
    summary,
    confidence,
    safe: isReadOnlySql(sql),
    generatedAt: new Date().toISOString(),
  };
}

export function runNaturalLanguageQuery(question, records) {
  const normalized = question.trim();
  if (!normalized) {
    return buildResult({
      intent: '等待输入',
      sql: 'SELECT * FROM sales_order LIMIT 0;',
      explanation: '请输入一个经营分析问题，系统会识别指标、维度、时间和筛选条件。',
      rows: [],
      summary: '尚未输入查询问题。',
      confidence: 0,
    });
  }

  if (/华东.*最高.*产品|最高.*产品.*华东/.test(normalized)) {
    const top = getTopProduct(records, { month: latestMonth, region: '华东' });
    return buildResult({
      intent: '按区域查询销售额最高产品',
      sql: "SELECT product_name, SUM(amount) AS sales_amount FROM sales_order WHERE month = '2026-06' AND region = '华东' GROUP BY product_name ORDER BY sales_amount DESC LIMIT 1;",
      explanation: `识别到时间=上月/最新月 ${latestMonth}，区域=华东，指标=销售额，排序=最高产品。`,
      rows: [top],
      summary: `华东区 ${latestMonth} 销售额最高的产品是 ${top.name}，销售额约 ${Math.round(top.amount)} 元。`,
    });
  }

  if (/各区域|区域.*排名|区域销售额/.test(normalized)) {
    const rows = getRegionComparison(records);
    return buildResult({
      intent: '区域销售额排名',
      sql: "SELECT region, SUM(amount) AS sales_amount FROM sales_order WHERE month = '2026-06' GROUP BY region ORDER BY sales_amount DESC;",
      explanation: `识别到维度=区域，指标=销售额，时间=最新月 ${latestMonth}。`,
      rows,
      summary: `最新月区域销售额排名第一的是 ${rows[0].name}，销售额约 ${Math.round(rows[0].amount)} 元。`,
    });
  }

  if (/最近30天|趋势/.test(normalized)) {
    const rows = weeklyTrend(records.filter((record) => record.month === latestMonth));
    return buildResult({
      intent: '最近 30 天销售趋势',
      sql: "SELECT week, SUM(amount) AS sales_amount FROM sales_order WHERE month = '2026-06' GROUP BY week ORDER BY week;",
      explanation: `识别到时间=最近 30 天，演示数据按 ${latestMonth} 周维度聚合。`,
      rows,
      chartType: 'line',
      summary: `最近 30 天销售额整体保持高位，${rows.at(-1).name} 销售额为 ${Math.round(rows.at(-1).amount)} 元。`,
    });
  }

  if (/毛利|利润/.test(normalized)) {
    const rows = rankingBy(records.filter((record) => record.month === latestMonth), 'category', 'profit');
    return buildResult({
      intent: '产品类别毛利排名',
      sql: "SELECT category, SUM(profit) AS profit, SUM(profit) / SUM(amount) AS profit_rate FROM sales_order WHERE month = '2026-06' GROUP BY category ORDER BY profit DESC;",
      explanation: '识别到指标=毛利，维度=产品类别，时间=最新月。',
      rows,
      summary: `最新月毛利最高的类别是 ${rows[0].name}，毛利约 ${Math.round(rows[0].profit)} 元。`,
    });
  }

  if (/本周.*上周|订单量.*下降/.test(normalized)) {
    const rows = weeklyTrend(records.filter((record) => record.month === latestMonth));
    const latest = rows.at(-1);
    const previous = rows.at(-2);
    const delta = previous?.quantity ? (latest.quantity - previous.quantity) / previous.quantity : 0;
    return buildResult({
      intent: '本周与上周订单量对比',
      sql: "SELECT week, COUNT(id) AS order_count, SUM(quantity) AS quantity FROM sales_order WHERE month = '2026-06' GROUP BY week ORDER BY week DESC LIMIT 2;",
      explanation: '识别到指标=订单量/销售数量，对比周期=本周与上周。',
      rows: [previous, latest],
      summary: delta < 0 ? `本周销售数量较上周下降 ${(Math.abs(delta) * 100).toFixed(1)}%。` : `本周销售数量较上周增长 ${(delta * 100).toFixed(1)}%。`,
    });
  }

  if (/为什么|原因|归因|华南/.test(normalized)) {
    const anomaly = detectAnomalies(records).find((item) => item.region === '华南') || detectAnomalies(records)[0];
    return buildResult({
      intent: '异常归因分析',
      sql: "SELECT region, product_name, customer_type, SUM(amount) AS sales_amount FROM sales_order WHERE month IN ('2026-05','2026-06') AND region = '华南' GROUP BY region, product_name, customer_type;",
      explanation: `识别到分析对象=华南区销售额波动，对比周期=${previousMonth} vs ${latestMonth}。`,
      rows: [anomaly],
      summary: anomaly?.reason || '未发现显著异常。',
    });
  }

  if (/下个月|预测|预计/.test(normalized)) {
    const forecast = forecastNextMonth(records);
    return buildResult({
      intent: '销售额趋势预测',
      sql: "SELECT month, SUM(amount) AS sales_amount FROM sales_order GROUP BY month ORDER BY month;",
      explanation: '识别到预测对象=下个月销售额，使用历史月度趋势做演示预测。',
      rows: [forecast],
      chartType: 'line',
      summary: `预计 ${forecast.label} 销售额约 ${forecast.predictedAmount} 元，预测仅供经营分析参考。`,
    });
  }

  if (/如果|假设|价格|促销/.test(normalized)) {
    const scenario = runScenario(records);
    return buildResult({
      intent: '假设分析',
      sql: "SELECT region, SUM(amount) AS base_amount FROM sales_order WHERE month = '2026-06' AND region = '华东' GROUP BY region;",
      explanation: '识别到假设条件=促销投入增加、价格下降，影响指标=销售额。',
      rows: [scenario],
      summary: scenario.explanation,
    });
  }

  const rows = rankingBy(filterRecords(records, { month: latestMonth }), 'productName', 'amount').slice(0, 5);
  return buildResult({
    intent: '通用产品销售排行',
    sql: "SELECT product_name, SUM(amount) AS sales_amount FROM sales_order WHERE month = '2026-06' GROUP BY product_name ORDER BY sales_amount DESC LIMIT 5;",
    explanation: `暂未完全匹配该问法，已回退到最新月 ${latestMonth} 产品销售排行。`,
    rows,
    summary: `系统可识别销售额、订单量、区域、产品、毛利、趋势、异常和预测类问题。当前返回最新月产品销售排行。`,
    confidence: 0.52,
  });
}

export function getDashboardSnapshot(records) {
  const latestRecords = records.filter((record) => record.month === latestMonth);
  return {
    kpis: getKpis(latestRecords),
    regions: getRegionComparison(records),
    products: rankingBy(latestRecords, 'productName', 'amount'),
    categories: rankingBy(latestRecords, 'category', 'profit'),
    anomalies: detectAnomalies(records),
    forecast: forecastNextMonth(records),
  };
}
