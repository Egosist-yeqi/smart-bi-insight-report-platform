export function executeQueryRequest(request, execute, options) {
  if (request === null) return Promise.resolve(null);
  return execute(request.question, options);
}
