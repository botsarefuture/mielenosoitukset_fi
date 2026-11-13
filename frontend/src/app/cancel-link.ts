// Organizer cancellation page, GET /cancel_demonstration/<token>. The copy is the
// Flask template's Finnish msgids. Token checks stay in Go (read) and Flask
// (the POST that cancels or requests cancellation and marks the token used).
export const cancelLinkTitle = 'Mielenosoituksen peruminen';
export const cancelLinkLead = 'Tämä linkki on tarkoitettu mielenosoituksen järjestäjille.';

export const cancelLinkErrors = {
  invalid: 'Peruutuslinkkiä ei tunnistettu.',
  expired: 'Peruutuslinkki on vanhentunut.',
  used: 'Peruutuslinkki on jo käytetty.',
  'missing-demonstration': 'Mielenosoitusta ei löytynyt.',
} as const;

export type CancelLinkState = {
  state: keyof typeof cancelLinkErrors;
} | {
  state: 'ready';
  demo: { title: string; date: string; city: string; cancelled: boolean };
  cancellationPending: boolean;
  canCancelDirectly: boolean;
};

export const cancelLinkTokenPattern = /^[A-Za-z0-9_-]{1,128}$/;

/** `unavailable` is a failed read: the page is not rendered as if the link were bad. */
export async function loadCancelLink(readBase: string, token: string): Promise<CancelLinkState | { state: 'unavailable' }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1500);
  try {
    const response = await fetch(`${readBase}/cancellation-links/${encodeURIComponent(token)}`, { signal: controller.signal });
    if (!response.ok) return { state: 'unavailable' };
    const payload = await response.json();
    if (payload?.state in cancelLinkErrors) return { state: payload.state };
    const demo = payload?.demo;
    if (payload?.state !== 'ready' || typeof demo?.title !== 'string' || typeof demo.date !== 'string'
      || typeof demo.city !== 'string' || typeof demo.cancelled !== 'boolean') return { state: 'unavailable' };
    return { state: 'ready', demo: { title: demo.title, date: demo.date, city: demo.city, cancelled: demo.cancelled },
      cancellationPending: payload.cancellation_pending === true, canCancelDirectly: payload.can_cancel_directly === true };
  } catch {
    return { state: 'unavailable' };
  } finally {
    clearTimeout(timer);
  }
}
