import test from 'node:test';
import assert from 'node:assert/strict';
import { salesRecords } from '../src/data/sampleData.js';
import { isReadOnlySql, runNaturalLanguageQuery } from '../src/lib/queryEngine.js';
import { generateReport } from '../src/lib/reporting.js';

test('Text-to-SQL demo returns a safe top product query', () => {
  const result = runNaturalLanguageQuery('上月华东区销售额最高的产品是什么？', salesRecords);

  assert.equal(result.intent, '按区域查询销售额最高产品');
  assert.equal(result.safe, true);
  assert.equal(result.rows[0].name, '星云 Pro 智能终端');
  assert.match(result.sql, /^SELECT/i);
});

test('SQL safety checker rejects destructive statements', () => {
  assert.equal(isReadOnlySql('SELECT * FROM sales_order'), true);
  assert.equal(isReadOnlySql('DELETE FROM sales_order'), false);
  assert.equal(isReadOnlySql('SELECT * FROM sales_order; DROP TABLE sales_order'), false);
});

test('Report generation includes selected modules', () => {
  const report = generateReport(salesRecords, {
    type: '月报',
    modules: ['overview', 'region', 'forecast'],
  });

  assert.match(report.markdown, /销售概览/);
  assert.match(report.markdown, /区域分析/);
  assert.match(report.markdown, /趋势预测/);
  assert.equal(report.sections.length, 3);
});
