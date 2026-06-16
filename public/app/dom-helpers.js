export async function copyToClipboardText(text) {
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    await navigator.clipboard.writeText(text);
    return;
  }

  const el = document.createElement('textarea');
  el.value = text;
  el.setAttribute('readonly', '');
  el.style.position = 'absolute';
  el.style.left = '-9999px';
  document.body.append(el);
  el.select();
  document.execCommand('copy');
  el.remove();
}

export function applyStatusTone(el, rawValue) {
  if (!el) return;
  const value = String(rawValue || '').toLowerCase();
  const positive = ['ok', 'reachable', 'available', 'read-only', 'none', 'unknown'];
  const negative = ['unreachable', 'failed', 'degraded', 'denied', 'error'];

  const isNegative = negative.some((token) => value.includes(token));
  const isPositive = positive.some((token) => value.includes(token));

  el.classList.toggle('status-bad', isNegative);
  el.classList.toggle('status-ok', !isNegative && isPositive);
}

export function appendReceiptField(container, label, value, receiptFieldFn) {
  const row = document.createElement('div');
  row.className = 'receipt-field';

  const key = document.createElement('span');
  key.className = 'receipt-field-key';
  key.textContent = `${label}:`;

  const val = document.createElement('span');
  val.className = 'receipt-field-value';
  val.textContent = receiptFieldFn(value);

  row.append(key, val);
  container.append(row);
}
