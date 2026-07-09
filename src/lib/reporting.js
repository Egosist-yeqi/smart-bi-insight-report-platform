import { detectAnomalies, forecastNextMonth, getKpis, getRegionComparison, rankingBy } from './analytics.js';
import { latestMonth } from '../data/sampleData.js';
import { formatCurrency, formatDelta, formatNumber, formatPercent } from './formatters.js';

export function generateReport(records, { type = '月报', modules = [] } = {}) {
  const latestRecords = records.filter((record) => record.month === latestMonth);
  const kpis = getKpis(latestRecords);
  const regions = getRegionComparison(records);
  const products = rankingBy(latestRecords, 'productName', 'amount');
  const anomalies = detectAnomalies(records);
  const forecast = forecastNextMonth(records);
  const selected = new Set(modules);

  const sections = [];
  if (selected.has('overview')) {
    sections.push({
      title: '销售概览',
      content: `${latestMonth} 销售额 ${formatCurrency(kpis.amount)}，销售数量 ${formatNumber(kpis.quantity)}，客单价 ${formatCurrency(kpis.avgOrderValue)}，毛利率 ${formatPercent(kpis.profitRate)}。`,
    });
  }
  if (selected.has('region')) {
    const topRegion = regions[0];
    sections.push({
      title: '区域分析',
      content: `${topRegion.name} 是当前销售额最高区域，销售额 ${formatCurrency(topRegion.amount)}，较上月变化 ${formatDelta(topRegion.delta)}。`,
    });
  }
  if (selected.has('ranking')) {
    sections.push({
      title: '产品排行',
      content: `销售额最高产品为 ${products[0].name}，销售额 ${formatCurrency(products[0].amount)}；前三产品贡献明显，是后续经营跟进重点。`,
    });
  }
  if (selected.has('anomaly')) {
    sections.push({
      title: '异常指标',
      content: anomalies.length
        ? anomalies.map((item) => `${item.region} ${item.metric} ${formatDelta(item.delta)}：${item.reason}`).join('；')
        : '本周期未发现超过阈值的显著异常波动。',
    });
  }
  if (selected.has('forecast')) {
    sections.push({
      title: '趋势预测',
      content: `预计 ${forecast.label} 销售额约 ${formatCurrency(forecast.predictedAmount)}，预测变化 ${formatDelta(forecast.growth)}。${forecast.basis}`,
    });
  }

  const title = `${latestMonth} 智能 BI 经营分析${type}`;
  const markdown = [
    `# ${title}`,
    '',
    `生成时间：${new Date().toLocaleString('zh-CN')}`,
    '',
    ...sections.flatMap((section) => [`## ${section.title}`, '', section.content, '']),
    '## 说明',
    '',
    '本报告由演示数据和本地规则生成，预测与归因结果用于原型验证，不代表生产环境结论。',
  ].join('\n');

  return { title, sections, markdown };
}
