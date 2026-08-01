import { expect, test as base } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const question = '上月华东区销售额最高的产品是什么？';
const regionalRankingQuestion = '本月各区域销售额排名如何？';
const qaPath = (name) => fileURLToPath(new URL(`../../文档/qa/${name}`, import.meta.url));
const healthOutageTest = 'shows a database outage reported by the health endpoint';

const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    const consoleErrors = [];
    const pageErrors = [];
    const requestFailures = [];
    const failedResponses = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });
    page.on('pageerror', (error) => pageErrors.push(error.message));
    page.on('requestfailed', (request) => {
      requestFailures.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`);
    });
    page.on('response', (response) => {
      if (response.status() >= 400) failedResponses.push(`${response.status()} ${response.url()}`);
    });

    await use(page);

    const allowsHealthOutage = testInfo.title === healthOutageTest;
    const unexpectedConsoleErrors = allowsHealthOutage
      ? consoleErrors.filter((message) => !message.includes('503'))
      : consoleErrors;
    const unexpectedResponses = allowsHealthOutage
      ? failedResponses.filter((response) => !response.startsWith('503 ') || !response.includes('/api/health'))
      : failedResponses;
    expect(unexpectedConsoleErrors, 'unexpected browser console errors').toEqual([]);
    expect(pageErrors, 'unexpected uncaught page errors').toEqual([]);
    expect(requestFailures, 'unexpected failed browser requests').toEqual([]);
    expect(unexpectedResponses, 'unexpected HTTP error responses').toEqual([]);
  },
});

async function openView(page, name) {
  await page.getByRole('button', { name, exact: true }).first().click();
}

test('serves production assets, SPA fallback, and the backend through Nginx', async ({ request }) => {
  const indexResponse = await request.get('/');
  expect(indexResponse.status()).toBe(200);
  expect(indexResponse.headers()['server']).toContain('nginx');
  expect(indexResponse.headers()['content-type']).toContain('text/html');
  const indexHtml = await indexResponse.text();
  const assetPath = indexHtml.match(/src="(\/assets\/[^"]+\.js)"/)?.[1];
  expect(assetPath).toBeTruthy();

  const assetResponse = await request.get(assetPath);
  expect(assetResponse.status()).toBe(200);
  expect(assetResponse.headers()['content-type']).toContain('javascript');
  expect((await assetResponse.body()).byteLength).toBeGreaterThan(1_000);

  const fallbackResponse = await request.get('/query/history/deep-link');
  expect(fallbackResponse.status()).toBe(200);
  expect(fallbackResponse.headers()['content-type']).toContain('text/html');
  expect(await fallbackResponse.text()).toContain('<div id="root"></div>');

  const healthResponse = await request.get('/api/health');
  expect(healthResponse.status()).toBe(200);
  expect((await healthResponse.json()).data).toMatchObject({
    app: 'up',
    database: 'up',
    seeded_orders: 540,
  });
});

test('does not query on mount or refresh before a user runs it', async ({ page }) => {
  let queryPosts = 0;
  await page.route((url) => url.pathname === '/api/query', async (route) => {
    queryPosts += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          intent: { metric: 'amount' },
          engine: 'local',
          provenance: 'local',
          warning: null,
          safe: true,
          sql: 'SELECT 1',
          rows: [],
          chart_type: 'bar',
          summary: '用户已运行查询。',
          data_as_of: null,
          data_period: '暂无可用数据',
          query_period: '暂无可用数据',
          answer: null,
        },
        request_id: 'explicit-query-only',
      }),
    });
  });

  const initialHistory = page.waitForResponse((response) => (
    response.url().includes('/api/query-history?limit=20') && response.status() === 200
  ));
  await page.goto('/');
  await initialHistory;
  await expect(page.getByText('输入问题后运行查询')).toBeVisible();
  await page.waitForTimeout(250);
  expect(queryPosts).toBe(0);

  const refreshedHistory = page.waitForResponse((response) => (
    response.url().includes('/api/query-history?limit=20') && response.status() === 200
  ));
  await page.reload();
  await refreshedHistory;
  await page.waitForTimeout(250);
  expect(queryPosts).toBe(0);

  await page.getByRole('button', { name: '运行查询', exact: true }).click();
  await expect.poll(() => queryPosts).toBe(1);
});

test.describe.serial('full-stack BI acceptance', () => {
  test('drives dashboard, local analytics, mock AI, and local fallback', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('MySQL 正常')).toBeVisible();

    await openView(page, '仪表盘');
    await expect(page.locator('.metric-card').first()).toBeVisible();
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
    await page.locator('.command-bar input').fill(question);
    await page.getByRole('button', { name: '运行查询', exact: true }).click();
    await expect(page.locator('.sql-box')).toContainText('SELECT');
    await expect(page.locator('.result-summary')).toContainText('只读 SQL 校验');
    await expect(page.locator('.query-result')).toBeVisible();
    await expect(page.locator('.panel').filter({ hasText: '推荐图表' }).locator('.bar-chart, .line-chart')).toBeVisible();
    await expect(page.locator('table')).toBeVisible();
    const csvDownloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: '导出 CSV', exact: true }).click();
    const csvDownload = await csvDownloadPromise;
    expect(csvDownload.suggestedFilename()).toBe('query-result.csv');
    const csvPath = await csvDownload.path();
    expect(csvPath).not.toBeNull();
    const csvContent = await readFile(csvPath, 'utf8');
    expect(csvContent).toContain('product_name,metric_value');

    const historyRefresh = page.waitForResponse((response) => (
      response.url().includes('/api/query-history?limit=20') && response.status() === 200
    ));
    await page.locator('.command-bar input').fill(regionalRankingQuestion);
    await page.getByRole('button', { name: '运行查询', exact: true }).click();
    await historyRefresh;
    const historyPanel = page.locator('.query-history');
    const newestHistory = historyPanel.locator('.query-history__item').first();
    await expect(newestHistory.locator('.query-history__question')).toHaveText(regionalRankingQuestion);
    await expect(newestHistory.locator('.query-history__engine')).toHaveText('本地');
    await expect(newestHistory.locator('.query-history__status')).toHaveText('成功');
    await expect(newestHistory.locator('.query-history__summary')).not.toBeEmpty();
    await expect(newestHistory.locator('time')).not.toBeEmpty();
    await expect(historyPanel).not.toContainText('SELECT');
    await expect(historyPanel).not.toContainText('filter_region');
    await expect(historyPanel).not.toContainText('parameters_json');

    await openView(page, '报告生成');
    for (const label of ['产品排行', '异常指标', '趋势预测']) {
      await page.getByLabel(label).uncheck();
    }
    await page.getByRole('button', { name: '生成报告', exact: true }).click();
    await expect(page.locator('.report-preview article')).toHaveCount(2);
    await expect(page.getByText('本地分析', { exact: true })).toBeVisible();
    const markdownDownloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: '导出 Markdown', exact: true }).click();
    const markdownDownload = await markdownDownloadPromise;
    expect(markdownDownload.suggestedFilename()).toBe('2026-06-01_2026-06-27-智能BI经营分析报告.md');
    const markdownPath = await markdownDownload.path();
    expect(markdownPath).not.toBeNull();
    const markdownContent = await readFile(markdownPath, 'utf8');
    expect(markdownContent).toContain('# 2026-06-01/2026-06-27 智能 BI 经营分析月报');
    expect(markdownContent).toContain('## 销售概览');
    expect(markdownContent).toContain('## 区域分析');

    await openView(page, '异常归因');
    await expect(page.locator('.panel-note')).toContainText('组织变化来自已完成月度聚合');
    await expect(page.locator('table')).toBeVisible();

    await openView(page, '行动中心');
    await page.getByRole('button', { name: '载入草案', exact: true }).first().click();
    await page.getByLabel('负责人').fill('区域运营负责人');
    await page.getByLabel('截止日期').fill('2026-07-15');
    await page.getByRole('button', { name: '创建待确认行动', exact: true }).click();
    await expect(page.getByText('行动项已创建，等待负责人确认执行。')).toBeVisible();
    await expect(page.getByText('待确认', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: '标记为执行中', exact: true }).click();
    await expect(page.getByText('执行中', { exact: true })).toBeVisible();
    await page.getByLabel('复盘结论').fill('已完成区域与项目结构核查，后续按周复盘。');
    await page.getByRole('button', { name: '完成并复盘', exact: true }).click();
    await expect(page.getByText('已复盘', { exact: true })).toBeVisible();
    await expect(page.getByText('已完成区域与项目结构核查，后续按周复盘。')).toBeVisible();

    await openView(page, '趋势预测');
    await expect(page.getByText(/预测仅供参考。/)).toBeVisible();
    await expect(page.locator('.forecast-number')).toBeVisible();

    await openView(page, '系统配置');
    await expect(page.getByLabel('AI 服务类型')).toHaveValue('deepseek');
    await expect(page.getByLabel('Base URL')).toHaveCount(0);
    await page.getByLabel('AI 服务类型').selectOption('custom');
    await page.getByLabel('服务名称').fill('Mock LLM');
    await page.getByLabel('Base URL').fill('http://mock-llm:8090/v1');
    await page.getByLabel('模型').fill('mock-model');
    await page.getByLabel('API 密钥').fill('test-key');
    await page.getByLabel('允许访问私有网络地址').check();
    await page.getByRole('button', { name: '保存配置', exact: true }).click();
    await expect(page.getByText('保存成功')).toBeVisible();
    await expect(page.getByText('te...ey')).toBeVisible();
    await expect(page.locator('.config-grid')).not.toContainText('test-key');

    const connectionRequest = page.waitForRequest((request) => (
      request.url().endsWith('/api/settings/ai/test') && request.method() === 'POST'
    ));
    await page.getByRole('button', { name: '连接测试', exact: true }).click();
    expect((await connectionRequest).postDataJSON()).toEqual({
      provider_name: 'Mock LLM',
      base_url: 'http://mock-llm:8090/v1',
      api_key: '',
      model: 'mock-model',
      timeout_seconds: 30,
      enabled: true,
      allow_private_network: true,
    });
    await expect(page.getByText(/已连接 Mock LLM \/ mock-model/)).toBeVisible();
    await page.screenshot({ path: qaPath('full-stack-ai-settings.png'), fullPage: true });

    await openView(page, '智能查询');
    await page.locator('.command-bar input').fill(question);
    await page.getByRole('button', { name: '运行查询', exact: true }).click();
    await expect(page.getByText('AI 解析结果已通过只读 SQL 校验。')).toBeVisible();

    await openView(page, '系统配置');
    await page.getByRole('button', { name: '删除配置', exact: true }).click();
    await expect(page.getByText('删除成功')).toBeVisible();
    await expect(page.locator('.panel').filter({ hasText: 'AI 服务配置' }).locator('.panel-header > span')).toHaveText('本地分析');
  });

  test('keeps the query workflow usable at a mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await expect(page.locator('.topbar')).toBeInViewport();
    await expect(page.getByRole('button', { name: '运行查询', exact: true })).toBeVisible();
    await expect(page.locator('.nav-item')).toHaveCount(8);
    await expect(page.locator('.nav-list')).toHaveCSS('overflow-x', 'auto');
    await page.getByRole('button', { name: question, exact: true }).click();
    await expect(page.locator('.sql-box')).toContainText('SELECT');
    const historyPanel = page.locator('.query-history');
    await historyPanel.scrollIntoViewIfNeeded();
    await expect(historyPanel.locator('.query-history__item').first()).toBeVisible();
    const panelBox = await historyPanel.boundingBox();
    const itemBox = await historyPanel.locator('.query-history__item').first().boundingBox();
    const sidebarBox = await page.locator('.sidebar').boundingBox();
    expect(panelBox).not.toBeNull();
    expect(itemBox).not.toBeNull();
    expect(sidebarBox).not.toBeNull();
    expect(itemBox.x).toBeGreaterThanOrEqual(panelBox.x);
    expect(itemBox.x + itemBox.width).toBeLessThanOrEqual(panelBox.x + panelBox.width + 1);
    const sidebarOverlapsHistory = !(
      sidebarBox.y + sidebarBox.height <= itemBox.y
      || itemBox.y + itemBox.height <= sidebarBox.y
    );
    expect(sidebarOverlapsHistory).toBe(false);
    await page.screenshot({ path: qaPath('full-stack-mobile-query.png'), fullPage: true });
  });
});

test('shows stable loading and empty states for query history', async ({ page }) => {
  await page.route('**/api/query-history?limit=20', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 350));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [], request_id: 'empty-history' }),
    });
  });

  await page.goto('/');

  const historyPanel = page.locator('.query-history');
  await expect(historyPanel.getByRole('status')).toHaveText('正在加载查询历史...');
  await expect(historyPanel.getByText('暂无查询历史')).toBeVisible();
});

test('shows a retryable query history error without an uncaught browser failure', async ({ page }) => {
  await page.addInitScript(() => {
    const nativeFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const url = typeof input === 'string' ? input : input.url;
      if (url.includes('/api/query-history?limit=20')) {
        return Promise.reject(new TypeError('synthetic history network failure'));
      }
      return nativeFetch(input, init);
    };
  });

  await page.goto('/');

  const historyPanel = page.locator('.query-history');
  await expect(historyPanel.getByRole('alert')).toContainText('无法连接到后端服务。');
  await expect(historyPanel.getByRole('button', { name: '重试', exact: true })).toBeVisible();
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
  await page.getByRole('button', { name: '运行查询', exact: true }).click();

  await expect(page.getByText('AI 服务不可用，已切换到本地规则解析。')).toBeVisible();
  await expect(page.getByText('AI_TIMEOUT')).toBeVisible();
  await expect(page.getByText('本地回退结果已通过只读 SQL 校验。')).toBeVisible();

  await openView(page, '报告生成');
  await page.getByRole('button', { name: '生成报告', exact: true }).click();
  await expect(page.getByText('AI 叙述服务不可用，已保留本地报告内容。')).toBeVisible();
  await expect(page.getByText('AI_BAD_RESPONSE')).toBeVisible();
  await expect(page.getByText(/本地回退 · 2026-06-01\/2026-06-27/)).toBeVisible();
});
