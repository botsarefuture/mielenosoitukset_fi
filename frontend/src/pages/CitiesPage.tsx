import { useEffect, useRef, useState } from 'react';
import { cityKey, helsinkiDay, readCities } from '../app/cities';
import type { CitiesData } from '../app/cities';
import { useDayRollover } from '../components/cities/useDayRollover';
import { CityDirectory } from '../components/cities/CityDirectory';
import '../components/cities/cities.css';

function filters() {
  const query = new URLSearchParams(window.location.search);
  return { search: (query.get('q') ?? '').slice(0, 200), today: query.get('today') === '1' };
}

export default function CitiesPage({ initialData, endpoint }: { initialData: CitiesData | null; endpoint: string }) {
  const [data, setData] = useState(initialData);
  const [filter, setFilter] = useState(filters);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(!initialData);
  const request = useRef<AbortController | null>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  useDayRollover(data?.day ?? helsinkiDay());
  useEffect(() => {
    const restore = () => setFilter(filters());
    window.addEventListener('popstate', restore);
    return () => { window.removeEventListener('popstate', restore); request.current?.abort(); };
  }, []);
  function change(next: typeof filter, push = false) {
    setFilter(next);
    const query = new URLSearchParams(window.location.search);
    if (next.search) query.set('q', next.search); else query.delete('q');
    if (next.today) query.set('today', '1'); else query.delete('today');
    const url = `${window.location.pathname}${query.size ? `?${query}` : ''}`;
    window.history[push ? 'pushState' : 'replaceState']({ cityFilter: true }, '', url);
  }
  async function retry() {
    if (request.current) return;
    const controller = new AbortController(); request.current = controller;
    const timer = window.setTimeout(() => controller.abort(), 5000);
    setLoading(true); setFailed(false);
    try {
      const response = await fetch(endpoint, { credentials: 'omit', signal: controller.signal });
      if (!response.ok) throw new Error('Directory unavailable');
      const result = readCities(await response.json());
      if (!result) throw new Error('Invalid directory');
      setData(result);
      searchInput.current?.focus();
    } catch { setFailed(true); }
    finally { clearTimeout(timer); request.current = null; setLoading(false); }
  }
  const available = data?.cities ?? [];
  const rows = available.filter(city => (!filter.today || city.today_count > 0)
    && cityKey(city.name).includes(cityKey(filter.search)));
  const todayCities = available.filter(city => city.today_count > 0).length;
  return <article className="city-discovery">
    <header className="city-intro"><div><h1>Kaupungit</h1>
      <p>Valitse kaupunki ja löydä tulevat mielenosoitukset. Tänään järjestettävät tapahtumat näet yhdellä painalluksella.</p>
      <p className="city-scope-note">Lista ei kata kaikkia Suomen kuntia. Siinä näkyvät paikkakunnat, joilla on ollut tai on tulossa mielenosoituksia, sekä paikkakunnat, joilla palvelu on otettu käyttöön, esimerkiksi kun paikkakunnalle on nimetty kaupunkiadmin.</p></div>
      <a className="detail-button" href="/mielenosoitukset-tanaan">Mielenosoitukset tänään <span aria-hidden="true">→</span></a>
    </header>
    <section className="city-search-panel" aria-label="Etsi kaupunki">
      <form onSubmit={event => event.preventDefault()}>
        <label className="city-search-label" htmlFor="city-search-input">Etsi kaupunki</label>
        <div className="city-search-row"><input ref={searchInput} id="city-search-input" type="search" placeholder="Kirjoita kaupungin nimi" maxLength={200}
          value={filter.search} onChange={event => change({ ...filter, search: event.target.value })} aria-controls="city-directory" />
          {filter.search && <button className="detail-button detail-button--quiet" type="button" onClick={() => { change({ ...filter, search: '' }); searchInput.current?.focus(); }}>Tyhjennä haku</button>}</div>
      </form>
      <div className="city-filter-row" role="group" aria-label="Näytettävät kaupungit">
        <button className="detail-button" type="button" aria-pressed={!filter.today} onClick={() => change({ ...filter, today: false }, true)}>Kaikki kaupungit</button>
        <button className="detail-button" type="button" aria-pressed={filter.today} onClick={() => change({ ...filter, today: true }, true)}>Tänään tapahtumia{data ? ` (${todayCities})` : ''}</button>
      </div>
    </section>
    {loading && <p role="status">Ladataan kaupunkeja…</p>}
    {failed && <section className="city-error" role="alert"><p>Kaupunkien lataaminen epäonnistui. Yritä uudelleen.</p>
      <button className="detail-button" type="button" disabled={loading} onClick={() => void retry()}>Yritä uudelleen</button></section>}
    {data && <><p className="city-result-count" role="status" aria-live="polite">{rows.length} {rows.length === 1 ? 'kaupunki' : 'kaupunkia'}</p>
      <CityDirectory cities={rows} loading={loading} showJumpLinks={!filter.search} />
      {!rows.length && <section className="city-empty"><h2>{filter.today ? 'Ei tapahtumia tänään näissä kaupungeissa' : 'Kaupunkia ei löytynyt'}</h2>
        <p>Kokeile toista hakua tai näytä kaikki kaupungit.</p><button className="detail-button" type="button" onClick={() => { change({ search: '', today: false }, true); searchInput.current?.focus(); }}>Näytä kaikki kaupungit</button></section>}
    </>}
  </article>;
}
