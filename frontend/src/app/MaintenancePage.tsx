/** Also rendered without JavaScript during a public-site security lockdown. */
export function MaintenancePage() {
  return <main className="container-main-content">
    <h1>Palvelu on tilapäisesti suljettu</h1>
    <p>Julkinen sivusto ei ole juuri nyt käytettävissä. Yritä myöhemmin uudelleen.</p>
    <p><a href="/users/auth/login">Ylläpidon kirjautuminen</a></p>
  </main>;
}
