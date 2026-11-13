/**
 * Fundraising purpose copy, kept in one place so the fundraising page and
 * anything else that mentions the collection (for example the front-page bar)
 * use identical wording. The friendly text may be edited, but must never
 * narrow, widen or contradict the permit purposes in `officialPurpose`.
 */
export const fundraisingCopy = {
  /** Lead line under the page title. */
  lead: 'Pienkeräys Mielenosoitukset.fi:n tunnettuuden ja ylläpidon tueksi',
  /** Short line for other surfaces such as the front-page bar. */
  barLine: 'Noin 25 000 tarraa ja 12 banderollia ympäri Suomen',
  planTitle: 'Mitä keräyksellä tehdään?',
  planIntro: 'Suunnitelma on suuntaa antava: määrät ovat arvioita, eivät lupauksia.',
  stickersTitle: 'Tarroja yli 70 paikkakunnalle',
  stickersLead: 'Tarroja on suunnitteilla yhteensä noin 25 000. Isommille kaupungeille tulee suurempi erä:',
  stickerTiers: [
    { amount: 'Noin 1 000 tarraa', places: 'Turku, Jyväskylä, Oulu, Joensuu, Kuopio ja Kirkkonummi' },
    { amount: 'Noin 500 tarraa', places: 'Vaasa, Porvoo, Mikkeli, Kotka, Lappeenranta, Rovaniemi, Kokkola, Pori, Lahti ja Kouvola' },
    { amount: 'Noin 200, 100 tai 50 tarraa', places: 'pienemmät paikkakunnat' },
  ],
  bannersTitle: 'Banderolleja',
  banners: '12 banderollia: 8 Pride-banderollia ja 4 tavallista banderollia mielenosoituksiin ja tapahtumiin.',
  upkeepTitle: 'Palvelun pyörittäminen',
  upkeep: 'Palvelin ja sen huolto, tarvittavat asiantuntijapalvelut ja pienhankinnat pitävät Mielenosoitukset.fi:n toiminnassa.',
  purposeTitle: 'Mihin varat käytetään?',
  purposeIntro: 'Keräämme rahaa, jotta mielenosoitukset löytyvät ja palvelu pysyy toiminnassa.',
  primaryTitle: 'Ensisijaisesti',
  primary: [
    'Markkinointikampanja, joka tekee Mielenosoitukset.fi:tä tunnetuksi: tarrat, julisteet ja banderollit suunnitellaan, valmistetaan ja hankitaan.',
    'Kampanjan muut kulut, kuten matkakulut.',
    'Palvelun välttämättömät ylläpitokulut: palvelin ja sen huolto, tarvittavat asiantuntijapalvelut ja pienhankinnat.',
  ],
  secondaryTitle: 'Jos varoja jää yli',
  secondary: 'Jos varoja jää ensisijaisen käytön jälkeen, ne käytetään kansalaistoiminnan tukemiseen: mielenosoituksissa käytettävää välineistöä, kuten äänentoistolaitteita, hankitaan, kunnostetaan ja huolletaan järjestäjien yhteiseen käyttöön. Välineitä voidaan lainata Tampereen Tapahtuma- ja mediarenessanssi ry:n kautta.',
  officialTitle: 'Virallinen käyttötarkoitus',
  /** The permit's purposes, in Finnish. Check against the permit's exact wording. */
  officialPrimary: 'Kerätyt varat käytetään Mielenosoitukset.fi-palvelun tunnettuuden lisäämiseen tähtäävän markkinointikampanjan toteuttamiseen ja palvelun ylläpitoon. Varoilla katetaan markkinointimateriaalien, kuten tarrojen, julisteiden ja banderollien, suunnittelu-, valmistus- ja hankintakustannukset, kampanjan muut kulut, kuten matkakulut, sekä palvelun välttämättömät ylläpitokulut: palvelin ja ylläpito, tarvittavat asiantuntijapalvelut ja pienhankinnat.',
  officialSecondary: 'Mikäli varoja jää ensisijaisen käyttötarkoituksen toteuttamisen jälkeen, ne käytetään kansalaistoiminnan tukemiseen hankkimalla, kunnostamalla ja ylläpitämällä mielenosoituksissa käytettäviä välineitä, kuten äänentoistolaitteita, järjestäjien yhteiseen käyttöön. Välineitä voidaan lainata Tampereen Tapahtuma- ja mediarenessanssi ry:n kautta.',
} as const;
