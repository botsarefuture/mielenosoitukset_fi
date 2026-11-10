export const statusTitle = 'Palvelun tila';
export const statusLead = 'Mielenosoitukset.fi — reaaliaikainen tila';
export const statusUnavailable = 'Palvelun tilaa ei voitu hakea.';

export type ServiceStatus = {
  overall_ok: boolean;
  services: { name: 'Tietokanta'; status: 'ok' | 'err'; message: 'Yhteys kunnossa' | 'Ei vastaa' }[];
  updated_at: string;
  latency_ms: number;
};

export async function loadStatus(readBase: string): Promise<ServiceStatus | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1500);
  try {
    const response = await fetch(`${readBase}/status`, { signal: controller.signal });
    if (!response.ok) return null;
    const payload = await response.json();
    if (typeof payload?.overall_ok !== 'boolean' || !Array.isArray(payload.services) || payload.services.length !== 1
      || typeof payload.updated_at !== 'string' || !/^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2} UTC$/.test(payload.updated_at)
      || !Number.isSafeInteger(payload.latency_ms) || payload.latency_ms < 0) return null;
    const service = payload.services[0];
    if (service?.name !== 'Tietokanta' || !['ok', 'err'].includes(service.status)
      || service.message !== (service.status === 'ok' ? 'Yhteys kunnossa' : 'Ei vastaa')
      || payload.overall_ok !== (service.status === 'ok')) return null;
    return { overall_ok: payload.overall_ok,
      services: [{ name: service.name, status: service.status, message: service.message }],
      updated_at: payload.updated_at, latency_ms: payload.latency_ms };
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
