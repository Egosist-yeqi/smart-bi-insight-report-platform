import { formatCurrency, formatNumber, formatPercent } from '../lib/formatters.js';
import React from 'react';

function formatCell(key, value) {
  if (value === undefined || value === null) return '-';
  if (/amount|base|simulated|predicted/i.test(key)) return formatCurrency(value);
  if (/profitRate|growth|delta|netChange/i.test(key)) return formatPercent(value);
  if (/quantity|orderCount/i.test(key)) return formatNumber(value);
  return String(value);
}

const columnLabels = {
  name: '名称',
  amount: '销售额',
  quantity: '销售数量',
  profit: '毛利',
  profitRate: '毛利率',
  orderCount: '订单批次',
  previousAmount: '上月销售额',
  delta: '变化',
  region: '区域',
  metric: '指标',
  currentAmount: '当前值',
  level: '级别',
  reason: '说明',
  predictedAmount: '预测销售额',
  growth: '预测变化',
  label: '周期',
  base: '基准销售额',
  simulatedAmount: '模拟销售额',
  netChange: '净影响',
  explanation: '解释',
};

export default function DataTable({ rows }) {
  if (!rows?.length) {
    return <div className="empty-state">暂无查询结果</div>;
  }

  const columns = Object.keys(rows[0]).filter((key) => !['generatedAt'].includes(key));

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => <th key={column}>{columnLabels[column] || column}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.name || row.region || row.label || index}-${index}`}>
              {columns.map((column) => <td key={column}>{formatCell(column, row[column])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
