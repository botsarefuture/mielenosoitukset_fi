export const volunteerMessages = {
  required: 'Nimi ja sähköpostiosoite ovat pakollisia.',
  invalid: 'Tarkista korostetut tiedot ja yritä uudelleen.',
  success: 'Kiitos ilmoittautumisestasi! Tarkista sähköpostisi vahvistaaksesi ilmoittautumisen.',
  failed: 'Ilmoittautuminen epäonnistui. Yritä uudelleen.',
  network: 'Yhteys palveluun epäonnistui. Yritä myöhemmin uudelleen.',
  sending: 'Lähetetään…',
};

export const confirmationCopy = {
  success: {
    title: 'Ilmoittautumisesi on vahvistettu',
    description: 'Sähköpostiosoitteesi on vahvistettu ja ilmoittautumisesi on tallennettu.',
    detail: 'Kiitos kiinnostuksestasi kampanjaa kohtaan. Voit palata tutustumaan kampanjaan tai jatkaa etusivulle.',
  },
  invalid: {
    title: 'Vahvistuslinkki ei ole voimassa',
    description: 'Linkki on virheellinen tai se on jo käytetty.',
    detail: 'Jos vahvistit ilmoittautumisesi jo aiemmin, sitä ei tarvitse tehdä uudelleen. Tarvittaessa voit kysyä apua sähköpostitse.',
  },
  expired: {
    title: 'Vahvistuslinkki on vanhentunut',
    description: 'Ilmoittautumista ei voitu vahvistaa tällä linkillä.',
    detail: 'Voit palata kampanjasivulle. Jos tarvitset apua ilmoittautumisen kanssa, ota yhteyttä sähköpostitse.',
  },
} as const;
