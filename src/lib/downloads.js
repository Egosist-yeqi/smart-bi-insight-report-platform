export function sanitizeCsvCell(value) {
  const text = value === undefined || value === null ? '' : String(value);
  return /^\s*[=+\-@]/.test(text) ? `'${text}` : text;
}

function escapeCsv(value) {
  const text = sanitizeCsvCell(value);
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function rowsToCsv(rows) {
  if (!rows?.length) return '';
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  return [columns, ...rows.map((row) => columns.map((column) => escapeCsv(row[column])))]
    .map((line) => line.join(','))
    .join('\r\n');
}

export function createDownloadBlob(content, mime = 'text/plain;charset=utf-8') {
  return new Blob([`\ufeff${content}`], { type: mime });
}

export function downloadText(filename, content, mime = 'text/plain;charset=utf-8') {
  const blob = createDownloadBlob(content, mime);
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
