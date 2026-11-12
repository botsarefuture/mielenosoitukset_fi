// The public content catalog is Finnish. Keep page metadata and route aliases
// with the standalone app, alongside the React components that use the copy.
export const informationPages = {
  info: {
    path: '/info', title: 'Tietoa Mielenosoitukset.fi -sivustosta',
    description: 'Olemme riippumaton, voittoa tavoittelematon alusta, joka yhdistää kaikki Suomen mielenosoitukset yhteen paikkaan. Edistämme vapaata mielipiteenilmaisua ja helpotamme osallistumista yhteiskunnallisiin tapahtumiin.',
  },
  guides: {
    path: '/ohjeet', title: 'Ohjeet järjestäjille',
    description: 'Selkeät ohjeet mielenosoituksen ilmoittamiseen, tapahtumakuviin ja organisaatiotileihin.',
  },
  privacy: {
    path: '/privacy', title: 'Tietosuojaseloste',
    description: 'Tässä selosteessa kerromme, mitä henkilötietoja Mielenosoitukset.fi-palvelu käsittelee, miksi tietoja käsitellään ja miten voit käyttää oikeuksiasi.',
  },
  terms: {
    path: '/terms', title: 'Käyttöehdot',
    description: 'Näissä ehdoissa kerrotaan Mielenosoitukset.fi-palvelun käytön periaatteista.',
  },
  translations: {
    path: '/upcoming/translations/', title: 'Käännöshanke',
    description: 'Mielenosoitukset.fi -sivustoa ollaan parhaillaan kääntämässä englanniksi ja ruotsiksi! Tavoitteena on, että koko sivusto ja sen perustoiminnot toimivat useilla kielillä, jotta mielenosoitukset olisivat saavutettavampia kaikille Suomessa.',
  },
} as const;

export type InformationPage = keyof typeof informationPages;

export function informationPageForPath(path: string): InformationPage | undefined {
  if (path === '/ohjeet/') return 'guides';
  return (Object.keys(informationPages) as InformationPage[]).find(key => informationPages[key].path === path);
}
