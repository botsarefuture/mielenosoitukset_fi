import { statusTitle, statusLead, statusUnavailable, type ServiceStatus } from './status';
import './status.css';

export default function StatusScreen({ status }: { status: ServiceStatus | null }) {
  return <article className="public-page-shell service-status" aria-labelledby="status-title">
    <header className="service-status-header">
      <h1 id="status-title">{statusTitle}</h1><p>{statusLead}</p>
    </header>
    <p className={`service-status-summary service-status--${status?.overall_ok ? 'ok' : 'err'}`} role="status">
      {status ? (status.overall_ok ? 'Kaikki palvelut toimivat' : 'Jokin palvelu ei vastaa') : statusUnavailable}
    </p>
    {status && <>
      <dl className="service-status-list">{status.services.map(service => <div key={service.name}>
        <dt>{service.name}</dt><dd className={`service-status--${service.status}`}>{service.message}</dd>
      </div>)}</dl>
      <p className="service-status-meta">Päivitetty: {status.updated_at} · Viive {status.latency_ms} ms</p>
    </>}
    <p>Välimuistin ja tiedostovaraston tilaa ei tarkisteta.</p>
    <a className="detail-button" href="/demonstrations">Kaikki mielenosoitukset</a>
  </article>;
}
