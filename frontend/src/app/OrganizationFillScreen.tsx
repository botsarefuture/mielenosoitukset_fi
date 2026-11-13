import { useState } from 'react';
import type { PublicOrganization } from '../components/organization/types';
import './information/information.css';
import './organization-fill/organization-fill.css';

const platforms: Record<string, string> = {
  twitter: 'Twitter / X', instagram: 'Instagram', facebook: 'Facebook', mastodon: 'Mastodon', bluesky: 'Bluesky',
  tiktok: 'TikTok', youtube: 'YouTube', linkedin: 'LinkedIn', snapchat: 'Snapchat',
};

type SocialRow = { key: number; platform: string; url: string };

/** Anyone may suggest missing organization details; Flask stores the suggestion for review. */
export default function OrganizationFillScreen({ profile }: { profile: PublicOrganization }) {
  const [rows, setRows] = useState<SocialRow[]>(() =>
    Object.entries(profile.social_media_links).map(([platform, url], key) => ({ key, platform, url })));
  const [nextKey, setNextKey] = useState(rows.length);
  const socialCount = Object.keys(profile.social_media_links).length;
  const facts = [
    { icon: 'fa-building', text: profile.name, missing: false },
    { icon: 'fa-globe', text: profile.website || 'Verkkosivusto puuttuu', missing: !profile.website },
    { icon: 'fa-envelope', text: profile.email || 'Sähköposti puuttuu', missing: !profile.email },
    { icon: 'fa-image', text: profile.logo ? 'Logo lisätty' : 'Logo puuttuu', missing: !profile.logo },
    { icon: 'fa-share-nodes', text: socialCount ? `Sosiaalisen median linkkejä: ${socialCount}` : 'Sosiaalisen median linkit puuttuvat', missing: !socialCount },
  ];
  const orgPath = `/organization/${profile._id}`;
  return <article className="public-page-shell information-page org-fill-page" aria-labelledby="org-fill-title">
    <header className="public-page-header org-fill-header">
      <div className="org-fill-header__identity">
        <span className="org-fill-logo">
          {profile.logo
            ? <img src={profile.logo} alt={`Logo: ${profile.name}`} loading="lazy" decoding="async" referrerPolicy="no-referrer" />
            : <i className="fa-solid fa-building" aria-hidden="true" />}
        </span>
        <div className="public-page-header__content">
          <h1 className="public-page-header__title" id="org-fill-title">{profile.name}</h1>
          <p className="public-page-header__description">Auta täydentämään tämän organisaation profiilia. Ehdotukset tarkistetaan ennen kuin ne näkyvät sivustolla.</p>
        </div>
      </div>
    </header>

    <div className="org-fill-layout">
      <aside className="public-prose-card" aria-labelledby="org-fill-current-title">
        <h2 id="org-fill-current-title">Nykyiset tiedot</h2>
        <p>Täydennä vain ne kohdat, jotka tiedät. Voit myös korjata vanhentuneita tietoja.</p>
        <ul className="org-fill-facts">
          {facts.map(fact => <li key={fact.icon} className={fact.missing ? 'is-missing' : undefined}>
            <i className={`fa-solid ${fact.icon}`} aria-hidden="true" /><span>{fact.text}</span>
          </li>)}
        </ul>
      </aside>

      <section className="public-prose-card" aria-labelledby="org-fill-form-title">
        <h2 id="org-fill-form-title">Täydennä järjestön tietoja</h2>
        <p>Lähetä ehdotus organisaation perustiedoista, yhteystiedoista tai sosiaalisen median kanavista.</p>
        <form id="org-edit-form" className="org-fill-form" action={`${orgPath}/save_suggestion`} method="post">
          <fieldset>
            <legend>Perustiedot</legend>
            <div className="org-fill-grid">
              <label>Järjestön nimi<input type="text" name="name" defaultValue={profile.name} required /></label>
              <label>Verkkosivusto<input type="url" name="website" placeholder="https://esimerkki.fi" defaultValue={profile.website} /></label>
              <label>Logo URL<input type="url" name="logo" placeholder="https://esimerkki.fi/logo.png" defaultValue={profile.logo ?? ""} /></label>
              <label>Sähköposti<input type="email" name="email" placeholder="info@esimerkki.fi" defaultValue={profile.email} /></label>
              <label className="org-fill-wide">Kuvaus<textarea name="description" rows={5}
                placeholder="Kuvaile järjestön toimintaa, tavoitteita ja arvoja…" defaultValue={profile.description} /></label>
            </div>
          </fieldset>
          <fieldset>
            <legend>Sosiaaliset mediat</legend>
            <div className="org-fill-socials">
              {rows.map(row => <div key={row.key} className="org-fill-social">
                <select name="social_platform[]" defaultValue={row.platform} aria-label="Alusta">
                  <option value="">Valitse alusta</option>
                  {Object.entries(platforms).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
                <input type="url" name="social_url[]" placeholder="https://..." defaultValue={row.url} aria-label="Osoite" />
                <button type="button" className="org-fill-remove" aria-label="Poista alusta"
                  onClick={() => setRows(current => current.filter(item => item.key !== row.key))}>
                  <i className="fa-solid fa-xmark" aria-hidden="true" />
                </button>
              </div>)}
            </div>
            <button type="button" className="detail-button org-fill-add"
              onClick={() => { setRows(current => [...current, { key: nextKey, platform: '', url: '' }]); setNextKey(nextKey + 1); }}>
              <i className="fa-solid fa-plus" aria-hidden="true" /> Lisää alusta
            </button>
          </fieldset>
          <div className="detail-actions org-fill-actions">
            <button type="submit" className="detail-button detail-button--primary"><i className="fa-solid fa-floppy-disk" aria-hidden="true" /> Tallenna ehdotus</button>
            <a className="detail-button detail-button--danger" href={orgPath}>Peruuta</a>
          </div>
        </form>
      </section>
    </div>
  </article>;
}
