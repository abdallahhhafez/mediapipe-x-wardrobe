export async function ingestPhoto(file) {
  const fd = new FormData();
  fd.append('photo', file);
  const res = await fetch('/api/ingest', { method: 'POST', body: fd });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? 'pipeline_failed');
  }
  return res.json();
}

export async function commit(garments) {
  const res = await fetch('/api/commit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ garments }),
  });
  if (!res.ok) throw new Error('commit_failed');
  return res.json();
}

export async function fetchItems() {
  const res = await fetch('/api/items');
  return res.json();
}
