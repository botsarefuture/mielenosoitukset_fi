/** All data links pass this boundary before becoming executable browser URLs. */
export function safeHref(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value.trim()) return undefined;
  const href = value.trim();
  if (/[\u0000-\u001f\u007f]/.test(href) || href.startsWith('//') || href.includes('\\')) return undefined;
  if (href.startsWith('/') || href.startsWith('#')) return href;
  try {
    const parsed = new URL(href);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : undefined;
  } catch { return undefined; }
}

const allowed = new Set(['P', 'BR', 'UL', 'OL', 'LI', 'STRONG', 'B', 'EM', 'I', 'BLOCKQUOTE', 'H2', 'H3', 'H4', 'HR', 'CODE', 'PRE', 'A']);
const discard = new Set(['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED', 'FORM', 'INPUT', 'BUTTON', 'TEXTAREA', 'SELECT', 'TEMPLATE', 'SVG', 'MATH']);
/** Rebuild a small rich-text vocabulary; never copy attributes or input HTML. */
export function sanitizeDescription(value: string): string {
  const parsed = new DOMParser().parseFromString(value, 'text/html');
  const output = document.createElement('div');
  function append(source: Node, target: Node) {
    if (source.nodeType === Node.TEXT_NODE) { target.appendChild(document.createTextNode(source.textContent ?? '')); return; }
    if (!(source instanceof Element) || discard.has(source.tagName)) return;
    const element = allowed.has(source.tagName) ? document.createElement(source.tagName.toLowerCase()) : null;
    if (element && source.tagName === 'A') {
      const href = safeHref(source.getAttribute('href'));
      if (href) { element.setAttribute('href', href); element.setAttribute('rel', 'noopener noreferrer'); }
    }
    for (const child of source.childNodes) append(child, element ?? target);
    if (element) target.appendChild(element);
  }
  for (const child of parsed.body.childNodes) append(child, output);
  return output.innerHTML;
}

export function dateLabel(value: string | null, locale: string): string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return value ?? '';
  const date = new Date(`${value}T12:00:00Z`);
  if (!Number.isFinite(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Helsinki' }).format(date);
}
export function clockLabel(value: string | null): string {
  return value && /^\d{2}:\d{2}(?::\d{2})?$/.test(value) ? value.slice(0, 5) : '';
}
