import test from 'node:test';
import assert from 'node:assert/strict';

import { executeQueryRequest } from '../src/lib/queryRequest.js';

test('query requests execute only after an explicit user request exists', async () => {
  const calls = [];
  const execute = async (question, options) => {
    calls.push({ question, options });
    return { data: { rows: [] } };
  };

  assert.equal(await executeQueryRequest(null, execute, { signal: 'initial' }), null);
  assert.deepEqual(calls, []);

  const result = await executeQueryRequest(
    { question: '本月各区域销售额排名如何？' },
    execute,
    { signal: 'clicked' },
  );

  assert.deepEqual(result, { data: { rows: [] } });
  assert.deepEqual(calls, [{
    question: '本月各区域销售额排名如何？',
    options: { signal: 'clicked' },
  }]);
});
