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
    await page.getByRole('button', { name: question, exact: true }).click();
    await expect(page.locator('.sql-box')).toContainText('SELECT');
    await page.screenshot({ path: qaPath('full-stack-mobile-query.png'), fullPage: true });
  });
});
