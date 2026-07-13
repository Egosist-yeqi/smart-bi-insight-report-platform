import test from 'node:test';
import assert from 'node:assert/strict';
import { createApiClient } from '../src/lib/apiClient.js';
import { createDownloadBlob, rowsToCsv, sanitizeCsvCell } from '../src/lib/downloads.js';

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

test('CSV sanitizes formula-leading values after whitespace and preserves Chinese newlines', () => {
  assert.equal(sanitizeCsvCell(' \t=SUM(A1:A2)'), "' \t=SUM(A1:A2)");
  assert.equal(sanitizeCsvCell('+1'), "'+1");
  assert.equal(sanitizeCsvCell('-1'), "'-1");
  assert.equal(sanitizeCsvCell('@command'), "'@command");

  assert.equal(
    rowsToCsv([{ 名称: '华东', 公式: ' =1+1', 备注: '第一行\n第二行' }]),
    '名称,公式,备注\r\n华东,\' =1+1,"第一行\n第二行"',
  );
});

test('download blobs include a UTF-8 BOM', async () => {
  const blob = createDownloadBlob('中文内容', 'text/csv;charset=utf-8');
  const bytes = new Uint8Array(await blob.arrayBuffer());

  assert.deepEqual([...bytes.slice(0, 3)], [0xef, 0xbb, 0xbf]);
  assert.equal(new TextDecoder().decode(bytes), '中文内容');
  assert.equal(blob.type, 'text/csv;charset=utf-8');
});
