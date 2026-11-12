export const suggestionTitle = 'Ehdota muutosta mielenosoitukseen';
export const suggestionLead = 'Tällä lomakkeella voit korjata tietoja tai täydentää puuttuvia yksityiskohtia. Kirjoita vain ne asiat, jotka pitäisi muuttaa. HTML-koodia ei tarvitse käyttää missään kohdassa.';

export const suggestionFields = ['title', 'date', 'start_time', 'end_time', 'city', 'address', 'facebook',
  'tags', 'route', 'organizers', 'description_markdown'] as const;
export type SuggestionDemo = { id: string; fields: Record<typeof suggestionFields[number], string>; organizersCurrent?: string };

export async function loadSuggestion(readBase: string, id: string): Promise<
  { status: 'ready'; demo: SuggestionDemo } | { status: 'not-found' } | { status: 'unavailable' }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1500);
  try {
    const response = await fetch(`${readBase}/demonstrations/${encodeURIComponent(id)}`, { signal: controller.signal });
    if (response.status === 404) return { status: 'not-found' };
    if (!response.ok) return { status: 'unavailable' };
    const payload = await response.json();
    if (typeof payload?._id !== 'string' || !/^[a-f\d]{24}$/i.test(payload._id)) return { status: 'unavailable' };
    if (payload._id.toLowerCase() !== id.toLowerCase()) return { status: 'not-found' };
    if (!payload.suggestion
      || suggestionFields.some(field => typeof payload.suggestion[field] !== 'string')) return { status: 'unavailable' };
    const fields = Object.fromEntries(suggestionFields.map(field => [field,
      /^(none|null)$/i.test(payload.suggestion[field].trim()) ? '' : payload.suggestion[field]])) as SuggestionDemo['fields'];
    return { status: 'ready', demo: { id, fields,
      ...(typeof payload.suggestion.organizers_current === 'string' ? { organizersCurrent: payload.suggestion.organizers_current } : {}) } };
  } catch {
    return { status: 'unavailable' };
  } finally {
    clearTimeout(timer);
  }
}
