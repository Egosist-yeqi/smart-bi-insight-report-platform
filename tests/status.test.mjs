import test from 'node:test';
import assert from 'node:assert/strict';

import { statusText } from '../src/lib/status.js';

test('status uses dynamic health provider when settings state is unavailable', () => {
  const status = statusText(
    {
      data: { data: { database: 'up', seeded_orders: 540, ai_mode: 'ai', provider: 'Mock LLM' } },
      loading: false,
      error: null,
    },
    { data: null, loading: false, error: new Error('settings unavailable') },
  );

  assert.deepEqual(status, {
    database: 'MySQL 正常',
    analysis: 'Mock LLM',
    detail: '540 条销售订单',
  });
});

test('status remains compatible with local health responses', () => {
  const status = statusText(
    {
      data: { data: { database: 'up', seeded_orders: 0, ai_mode: 'local', provider: null } },
      loading: false,
      error: null,
    },
    { data: { data: { configured: false, ai_mode: 'local' } }, loading: false, error: null },
  );

  assert.equal(status.analysis, '本地分析');
  assert.equal(status.detail, '0 条销售订单');
});
