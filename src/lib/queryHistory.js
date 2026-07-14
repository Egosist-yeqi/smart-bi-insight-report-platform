export const QUERY_HISTORY_LIMIT = 20;

function createdTime(record) {
  const parsed = Date.parse(record?.created_at || '');
  return Number.isFinite(parsed) ? parsed : 0;
}

export function prepareQueryHistory(records) {
  return (Array.isArray(records) ? records : [])
    .filter((record) => typeof record?.question === 'string' && record.question.trim())
    .map((record, index) => ({ record, index }))
    .sort((left, right) => (
      createdTime(right.record) - createdTime(left.record)
      || Number(right.record.id || 0) - Number(left.record.id || 0)
      || left.index - right.index
    ))
    .slice(0, QUERY_HISTORY_LIMIT)
    .map(({ record }) => ({
      question: record.question,
      engine: record.engine === 'ai' ? 'ai' : 'local',
      status: record.status === 'succeeded' ? 'succeeded' : 'failed',
      summary: typeof record.summary === 'string' ? record.summary : '',
      createdAt: typeof record.created_at === 'string' ? record.created_at : '',
    }));
}
