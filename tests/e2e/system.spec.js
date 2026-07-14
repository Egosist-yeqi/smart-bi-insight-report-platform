import { expect, test } from '@playwright/test';
import { fileURLToPath } from 'node:url';

const question = '上月华东区销售额最高的产品是什么？';
const qaPath = (name) => fileURLToPath(new URL(`../../docs/qa/${name}`, import.meta.url));

async function openView(page, name) {
  await page.getByRole('button', { name, exact: true }).first().click();
}

test.describe.serial('full-stack BI acceptance', () => {
  test('drives dashboard, local analytics, mock AI, and local fallback', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('MySQL 正常')).toBeVisible();

    await openView(page, '仪表盘');
    await expect(page.getByText('销售额', { exact: true })).toBeVisible();
    await expect(page.locator('.metric-card').first().locator('strong')).toContainText(/¥|￥/);
    await expect(page.locator('.contribution-item').first()).not.toContainText(/NaN|undefined/);
    await expect(page.locator('.line-chart .chart-label')).toHaveCount(7);
    await page.screenshot({ path: qaPath('full-stack-dashboard.png'), fullPage: true });

    const regionFilter = page.getByLabel('区域');
    await expect(regionFilter).toContainText('华东');
    const dashboardResponse = page.waitForResponse((response) => (
      response.url().includes('/api/dashboard?') && response.status() === 200
    ));
    await regionFilter.selectOption('华东');
    await dashboardResponse;
    await expect(regionFilter).toHaveValue('华东');

    await openView(page, '智能查询');
    await page.getByRole('button', { name: question, exact: true }).click();
    await expect(page.locator('.sql-box')).toContainText('SELECT');
    await expect(page.locator('.result-summary')).toContainText('只读 SQL 校验');
    await expect(page.locator('.query-result')).toBeVisible();
    await expect(page.locator('.panel').filter({ hasText: '推荐图表' }).locator('.bar-chart, .line-chart')).toBeVisible();
    await expect(page.locator('table')).toBeVisible();

    await openView(page, '报告生成');
    for (const label of ['产品排行', '异常指标', '趋势预测']) {
      await page.getByLabel(label).uncheck();
    }
    await page.getByRole('button', { name: '生成报告', exact: true }).click();
    await expect(page.locator('.report-preview article')).toHaveCount(2);
    await expect(page.getByText('本地分析', { exact: true })).toBeVisible();

    await openView(page, '异常归因');
    await expect(page.getByText('区域变化来自已完成月度订单聚合')).toBeVisible();
    await expect(page.locator('table')).toBeVisible();

    await openView(page, '趋势预测');
    await expect(page.getByText(/预测仅供参考。/)).toBeVisible();
    await expect(page.getByText('预测值基于已完成月度销售额趋势')).toBeVisible();

    await openView(page, '系统配置');
    await page.getByLabel('服务名称').fill('Mock LLM');
    await page.getByLabel('Base URL').fill('http://mock-llm:8090/v1');
    await page.getByLabel('模型').fill('mock-model');
    await page.getByLabel('API 密钥').fill('test-key');
    await page.getByLabel('允许访问私有网络地址').check();
    await page.getByRole('button', { name: '保存配置', exact: true }).click();
    await expect(page.getByText('保存成功')).toBeVisible();
    await expect(page.getByText('te...ey')).toBeVisible();
    await expect(page.locator('.config-grid')).not.toContainText('test-key');

    await page.getByRole('button', { name: '连接测试', exact: true }).click();
    await expect(page.getByText(/已连接 Mock LLM \/ mock-model/)).toBeVisible();
    await page.screenshot({ path: qaPath('full-stack-ai-settings.png'), fullPage: true });

    await openView(page, '智能查询');
    await page.getByRole('button', { name: question, exact: true }).click();
    await expect(page.getByText('AI 解析结果已通过只读 SQL 校验。')).toBeVisible();

    await openView(page, '系统配置');
    await page.getByRole('button', { name: '删除配置', exact: true }).click();
    await expect(page.getByText('删除成功')).toBeVisible();
    await expect(page.locator('.panel').filter({ hasText: 'AI 服务配置' }).locator('.panel-header > span')).toHaveText('本地分析');
  });

  test('keeps the query workflow usable at a mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await expect(page.getByText('MySQL 正常')).toBeVisible();
    await expect(page.locator('.topbar')).toBeInViewport();
    await expect(page.locator('.nav-item')).toHaveCount(6);
    await expect(page.locator('.nav-list')).toHaveCSS('overflow-x', 'auto');
    await page.getByRole('button', { name: question, exact: true }).click();
    await expect(page.locator('.sql-box')).toContainText('SELECT');
    await page.screenshot({ path: qaPath('full-stack-mobile-query.png'), fullPage: true });
  });
});

test('shows a database outage reported by the health endpoint', async ({ page }) => {
  await page.route('**/api/health', (route) => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({
      error: {
        code: 'DATABASE_UNAVAILABLE',
        message: '数据库连接不可用。',
        details: { app: 'up', database: 'down', seeded_orders: 0, ai_mode: 'local' },
      },
      request_id: 'health-browser-test',
    }),
  }));

  await page.goto('/');

  await expect(page.getByText('MySQL 异常')).toBeVisible();
  await expect(page.getByText('数据库连接不可用。')).toBeVisible();
});

test('shows structured AI fallback for queries and reports', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const { pathname } = new URL(route.request().url());
    const envelopes = {
      '/api/health': {
        data: { app: 'up', database: 'up', seeded_orders: 540, ai_mode: 'local' },
        request_id: 'fallback-health',
      },
      '/api/settings/ai': {
        data: { configured: true, enabled: true, provider_name: 'Unavailable AI' },
        request_id: 'fallback-settings',
      },
      '/api/query': {
        data: {
          engine: 'local',
          provenance: 'local_fallback',
          warning: { code: 'AI_TIMEOUT', message: 'AI 服务不可用，已切换到本地规则解析。' },
          safe: true,
          sql: 'SELECT region, SUM(amount) FROM sales_order GROUP BY region',
          rows: [],
          chart_type: 'bar',
          summary: '本地查询结果。',
          data_period: '数据范围2025-01-01至2026-06-27',
          query_period: '2026-06',
        },
        request_id: 'fallback-query',
      },
      '/api/reports/generate': {
        data: {
          title: '本地回退报告',
          period: '2026-06-01/2026-06-27',
          sections: [{ id: 'overview', title: '销售概览', content: '本地报告内容。' }],
          markdown: '# 本地回退报告',
          engine: 'local',
          provenance: 'local_fallback',
          warning: { code: 'AI_BAD_RESPONSE', message: 'AI 叙述服务不可用，已保留本地报告内容。' },
        },
        request_id: 'fallback-report',
      },
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(envelopes[pathname]) });
  });

  await page.goto('/');

  await expect(page.getByText('AI 服务不可用，已切换到本地规则解析。')).toBeVisible();
  await expect(page.getByText('AI_TIMEOUT')).toBeVisible();
  await expect(page.getByText('本地回退结果已通过只读 SQL 校验。')).toBeVisible();

  await openView(page, '报告生成');
  await page.getByRole('button', { name: '生成报告', exact: true }).click();
  await expect(page.getByText('AI 叙述服务不可用，已保留本地报告内容。')).toBeVisible();
  await expect(page.getByText('AI_BAD_RESPONSE')).toBeVisible();
  await expect(page.getByText(/本地回退 · 2026-06-01\/2026-06-27/)).toBeVisible();
});
