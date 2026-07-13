function escapeCsv(value) {
  const text = value === undefined || value === null ? '' : String(value);
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function rowsToCsv(rows) {
  if (!rows?.length) return '';
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  return [columns, ...rows.map((row) => columns.map((column) => escapeCsv(row[column])))]
    .map((line) => line.join(','))
    .join('\r\n');
}

export function downloadText(filename, content, mime = 'text/plain;charset=utf-8') {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
