// Measure once before requesting people. Resizing never triggers background requests.
const list = document.querySelector('[data-viewport-page]');
if (list && !new URL(location.href).searchParams.has('limit')) {
  const row = list.querySelector('.search-result');
  const available = Math.max(0, innerHeight - list.getBoundingClientRect().top - 80);
  const rowHeight = row ? row.getBoundingClientRect().height + 15 : 100;
  const limit = Math.max(1, Math.min(24, Math.floor(available / rowHeight)));
  const target = new URL(location.href);
  target.searchParams.set('limit', String(limit));
  location.replace(target.href);
}
