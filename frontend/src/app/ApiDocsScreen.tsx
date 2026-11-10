export default function ApiDocsScreen({ html, toc }: { html: string; toc: string }) {
  return <article className="api-docs-wrap public-page-shell" aria-labelledby="api-docs-title">
    <header className="public-page-header">
      <div className="public-page-header__content">
        <h1 className="public-page-header__title" id="api-docs-title">API-dokumentaatio</h1>
        <p className="public-page-header__description">Ihmisluettava dokumentaatio julkiselle API:lle.</p>
      </div>
      <div className="public-page-header__meta api-docs-meta" aria-label="API:n perustiedot">
        <span>OpenAPI-määrittely: <a href="/api-docs/openapi.yaml">openapi.yaml</a></span>
        <span>Perusosoite: <code>/api</code></span>
      </div>
    </header>
    <div className="api-docs-layout">
      <aside className="api-docs-sidebar" aria-labelledby="api-docs-contents-title">
        <h2 id="api-docs-contents-title">Sisältö</h2>
        <nav aria-label="Sisältö" dangerouslySetInnerHTML={{ __html: toc }} />
      </aside>
      <div className="api-docs-content" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  </article>;
}
