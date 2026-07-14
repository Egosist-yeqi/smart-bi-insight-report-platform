import { defineConfig } from '@playwright/test';

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:8081';
const startLocalFrontend = !process.env.PLAYWRIGHT_BASE_URL;

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  outputDir: 'test-results',
  reporter: [['list']],
  use: {
    baseURL,
    viewport: { width: 1280, height: 900 },
    channel: 'chrome',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chrome', use: { browserName: 'chromium' } }],
  webServer: startLocalFrontend
    ? {
        command: 'npm.cmd run dev -- --port 8081 --strictPort',
        url: baseURL,
        reuseExistingServer: false,
        timeout: 30_000,
        env: {
          ...process.env,
          VITE_API_PROXY_TARGET: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8001',
        },
      }
    : undefined,
});
