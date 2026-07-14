import test from 'node:test';
import assert from 'node:assert/strict';
import { prepareQueryHistory, QUERY_HISTORY_LIMIT } from '../src/lib/queryHistory.js';

test('query history is newest-first, bounded, and projected to display-safe fields', () => {
  const records = Array.from({ length: QUERY_HISTORY_LIMIT + 2 }, (_, index) => ({
    id: index + 1,
    question: `问题 ${index + 1}`,
    engine: index % 2 ? 'ai' : 'local',
    status: index % 3 ? 'succeeded' : 'failed',
    summary: `摘要 ${index + 1}`,
    created_at: new Date(Date.UTC(2026, 0, index + 1)).toISOString(),
    generated_sql: `SELECT secret_${index}`,
    parameters_json: { api_key: `secret-${index}` },
  }));

  const history = prepareQueryHistory(records.reverse());

  assert.equal(history.length, QUERY_HISTORY_LIMIT);
  assert.equal(history[0].question, `问题 ${QUERY_HISTORY_LIMIT + 2}`);
  assert.equal(history.at(-1).question, '问题 3');
  assert.deepEqual(Object.keys(history[0]), [
    'question',
    'engine',
    'status',
    'summary',
    'createdAt',
  ]);
  assert.doesNotMatch(JSON.stringify(history), /SELECT|api_key|secret-/);
});
