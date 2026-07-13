import test from 'node:test';
import assert from 'node:assert/strict';
import { createApiClient } from '../src/lib/apiClient.js';

test('API client unwraps data and preserves request id', async () => {
  const client = createApiClient(async () => new Response(JSON.stringify({
    data: { app: 'up' },
    request_id: 'req-1',
  }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

  const result = await client.health();

  assert.deepEqual(result.data, { app: 'up' });
  assert.equal(result.requestId, 'req-1');
});

test('API client exposes normalized server errors', async () => {
  const client = createApiClient(async () => new Response(JSON.stringify({
    error: { code: 'AI_AUTH_FAILED', message: 'API key is invalid' },
    request_id: 'req-2',
  }), { status: 401, headers: { 'Content-Type': 'application/json' } }));

  await assert.rejects(client.testAi({}), (error) => {
    assert.equal(error.code, 'AI_AUTH_FAILED');
    assert.equal(error.requestId, 'req-2');
    return true;
  });
});
