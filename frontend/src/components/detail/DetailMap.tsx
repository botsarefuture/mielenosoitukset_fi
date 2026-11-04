import type { DetailMessages } from './types';

/** Loaded only on request. The iframe source is generated from validated numbers. */
export default function DetailMap({ latitude, longitude, messages }: { latitude: number; longitude: number; messages: DetailMessages }) {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return null;
  const bbox = [Math.max(-180, longitude - .012), Math.max(-90, latitude - .006), Math.min(180, longitude + .012), Math.min(90, latitude + .006)].join(',');
  const query = new URLSearchParams({ bbox, layer: 'mapnik', marker: `${latitude},${longitude}` });
  return <iframe className="detail-map" src={`https://www.openstreetmap.org/export/embed.html?${query}`}
    title={messages.map} loading="lazy" referrerPolicy="no-referrer" sandbox="allow-scripts allow-same-origin allow-popups" />;
}
