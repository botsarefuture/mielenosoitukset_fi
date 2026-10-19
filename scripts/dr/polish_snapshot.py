#!/usr/bin/env python3
"""Finish an anonymous snapshot for navigation without scripts or backend access.

Requires beautifulsoup4. Run on a COPY of the prepared crawl; input is the public
event API only. No account exports or authenticated pages belong in a snapshot.
"""
import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

from bs4 import BeautifulSoup

PREFIX = "/mirror/"
UNAVAILABLE = PREFIX + "palvelun-tila/"


def soup(value):
    return BeautifulSoup(value, "html.parser")


def local_target(root, href):
    """Resolve URL paths as nginx does, without permitting filesystem escape."""
    parsed = urlsplit(href)
    if parsed.netloc or not parsed.path.startswith(PREFIX):
        return None
    rel = unquote(parsed.path[len(PREFIX):])
    if ".." in Path(rel).parts:
        return None
    target = root / rel
    return target / "index.html" if target.is_dir() else target


def event_path(event):
    raw = str(event.get("slug") or event.get("running_number") or event["_id"])
    if raw in {"", ".", ".."} or any(c in raw for c in "/\\"):
        raise ValueError("Unsafe event identifier")
    return "demonstration/" + quote(raw, safe="") + "/"


def image_html(event, root):
    source = urlsplit(str(event.get("cover_picture") or event.get("img") or event.get("preview_image") or ""))
    path = source.path
    if source.hostname == "pentest.mielenosoitukset.fi" and path.startswith("/media/"):
        path = path.removeprefix("/media")
    elif source.hostname != "cdn2.mielenosoitukset.fi":
        return ""
    url = PREFIX + "_external/cdn2.mielenosoitukset.fi" + path
    target = local_target(root, url)
    if not target or not target.is_file():
        return ""
    return '<img class="dr-event-image" loading="lazy" src="' + escape(url, quote=True) + '" alt="">'


def cards(events, root):
    if not events:
        return ('<div class="dr-empty"><h3>Tähän näkymään ei tallentunut tapahtumia</h3>'
                '<p>Tallennettu otos ei kata koko tapahtuma-arkistoa.</p>'
                '<a href="/mirror/demonstrations/">Selaa tallennettuja tapahtumia →</a></div>')
    result = []
    for event in events:
        details = " · ".join(str(event.get(k) or "") for k in ["formatted_date", "start_time", "city"])
        result.append('<article class="dr-event">' + image_html(event, root) + '<p class="dr-eyebrow">' + escape(details) + '</p>'
                      '<h3><a href="' + PREFIX + event_path(event) + '">' + escape(event["title"]) + '</a></h3>'
                      '<p>' + escape(str(event.get("address") or "")) + '</p>'
                      '<a class="dr-event-link" href="' + PREFIX + event_path(event) + '">Tapahtuman tiedot →</a></article>')
    return '<div class="dr-events">' + "".join(result) + '</div>'


def shell(title, content):
    return soup('<!doctype html><html lang="fi"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>' + escape(title) + '</title></head><body><main id="main-content">' + content + '</main></body></html>')


def polish(root, response, stylesheet):
    root = Path(root)
    # nginx decodes URL paths. Store encoded crawl names in their decoded form.
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        decoded = unquote(path.name)
        if decoded != path.name:
            if decoded in {".", ".."} or "/" in decoded or "\\" in decoded:
                raise ValueError("Unsafe encoded crawl path")
            destination = path.with_name(decoded)
            if destination.exists():
                raise ValueError("Decoded crawl path collision")
            path.rename(destination)
    captured = datetime.fromisoformat(response.get("snapshot_captured_at") or datetime.now(timezone.utc).isoformat())
    snapshot_date = captured.astimezone(ZoneInfo("Europe/Helsinki")).strftime("%d.%m.%Y %H.%M")
    events = response["results"][:100]
    for event in events:
        description = soup(str(event.get("description") or "")).get_text("\n", strip=True)
        content = ('<section class="dr-detail"><p class="dr-eyebrow">Tapahtuman tiedot</p>'
                   + image_html(event, root) + '<h1>' + escape(event["title"]) + '</h1><p class="dr-lead">' + escape(" · ".join(
                       str(event.get(k) or "") for k in ["formatted_date", "start_time", "city", "address"])) + '</p>'
                   '<div class="dr-description">' + escape(description) + '</div>'
                   '<p><a href="/mirror/demonstrations/">← Kaikki tallennetut tapahtumat</a></p></section>')
        page = root / unquote(event_path(event)) / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(str(shell(event["title"], content)))
    status = root / "palvelun-tila/index.html"
    status.parent.mkdir(exist_ok=True)
    status.write_text(str(shell("Tietoa tallennetusta sivustosta", '''<section class="dr-detail">
      <p class="dr-eyebrow">Tallennettu sivusto</p><h1>Selaaminen toimii myös käyttökatkon aikana</h1>
      <p class="dr-lead">Voit lukea tallennettuja tapahtumia, kaupunkisivuja ja ohjeita.</p>
      <h2>Mitkä toiminnot odottavat varsinaista palvelua?</h2>
      <p>Kirjautuminen, ilmoitusten lisääminen, viestien lähettäminen ja reaaliaikainen haku tarvitsevat
      toimivan sovelluksen. Tässä näkymässä niitä ei lähetetä tai tallenneta.</p>
      <p>Tiedot voivat muuttua tallennuksen jälkeen. Tarkista järjestäjän ajantasaiset tiedot ennen osallistumista.
      Tallennettu tapahtumaotos ei kata koko arkistoa.</p>
      <div class="dr-actions"><a href="/mirror/demonstrations/">Selaa tapahtumia →</a>
      <a href="/mirror/cities/">Valitse kaupunki →</a></div></section>''')))
    pages = list(root.rglob("*.html"))
    repaired = redirects = 0
    for path in pages:
        page = soup(path.read_text())
        # Replace server redirect stubs with the saved destination's content.
        if page.title and "Redirecting" in page.title.get_text():
            link = page.find("a", href=True)
            target = local_target(root, link["href"]) if link else None
            if target and target.is_file() and target != path:
                candidate = soup(target.read_text())
                page = candidate if candidate.find("main") else soup(status.read_text())
            else:
                page = soup(status.read_text())
            redirects += 1
        if not page.find("main"):
            # Avoid publishing empty crawl/error documents as unfinished pages.
            page = soup(status.read_text())
        if not page.html:
            page = shell("Mielenosoitukset.fi", str(page))
        if not page.head:
            page.html.insert(0, page.new_tag("head"))
        if not page.body:
            body = page.new_tag("body")
            for child in list(page.html.contents):
                if child != page.head:
                    body.append(child.extract())
            page.html.append(body)
        for node in page.select('script, form, iframe, object, template, dialog, header, footer, nav.public-main-nav, .dr-banner, '
                                '[id="dr-public-events"], [id="listing-load-error"], '
                                '[id="listing-result-summary"], [id="no-results"], '
                                '[class*="cities-search"], [class*="friends-list"], [id*="friends-dialog"]'):
            node.decompose()
        for aside in page.find_all("aside"):
            if "TEST / DR" in aside.get_text():
                aside.decompose()
        for node in list(page.select('a[href="#dr-unavailable"]')):
            node["href"] = UNAVAILABLE
        for node in page.select('[id="map"]'):
            node.clear()
            node.append(soup('<p class="dr-note">Sijainnin osoite näkyy tapahtuman tiedoissa. Interaktiivinen kartta ei ole käytössä tallennetussa näkymässä.</p>'))
            node.attrs.pop("style", None)
        for grid in page.select('#featured-demos-grid, #demos-grid'):
            selected = events
            rel = path.relative_to(root).as_posix()
            if rel.startswith("city/"):
                city = rel.split("/")[1]
                import unicodedata
                def key(value):
                    return "".join(c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c))
                selected = [e for e in events if key(str(e.get("city", ""))).replace(" ", "-") == city]
            if grid.get("id") == "featured-demos-grid":
                selected = selected[:6]
            grid.clear()
            grid.append(soup(cards(selected, root)))
            for text in list(grid.parent.find_all(string=True, recursive=False)):
                if re.fullmatch(r"(?:(?:Edellinen|Näytä lisää|Yritä uudelleen)\s*)+", text.strip()):
                    text.extract()
        contact = page.select_one('#contact-form-section')
        if contact:
            contact.clear()
            contact.append(soup('<h2>Viestien lähetys on tauolla</h2><p>Tallennettu sivusto ei lähetä lomakeviestejä. '
                                'Voit sillä välin lukea <a href="/mirror/ohjeet/">ohjeet</a> tai '
                                '<a href="/mirror/palvelun-tila/">tiedot palvelun toiminnasta</a>.</p>'))
        # Decode Cloudflare's public email obfuscation without its remote script.
        for node in page.select('[data-cfemail]'):
            try:
                data = bytes.fromhex(node['data-cfemail'])
                node.string = bytes(b ^ data[0] for b in data[1:]).decode()
            except (ValueError, UnicodeDecodeError):
                node.string = "Yhteystiedot varsinaisessa palvelussa"
        for inner in page.select("main main"):
            inner.name = "section"
        for node in page.find_all(True):
            for attr in list(node.attrs):
                if attr.lower().startswith("on"):
                    del node[attr]
        for a in page.find_all("a", href=True):
            href = a['href']
            target = local_target(root, href)
            if href == '#dr-unavailable' or (href.startswith(PREFIX) and (not target or not target.is_file())):
                a['href'] = UNAVAILABLE
                repaired += 1
            elif href.startswith(PREFIX) and target.name == 'index.html':
                a['href'] = PREFIX + quote(target.parent.relative_to(root).as_posix(), safe='/') + '/'
                if a['href'] == '/mirror/./':
                    a['href'] = PREFIX
        for link in list(page.select('link[rel="stylesheet"]')):
            if not local_target(root, link.get('href', '')) or not local_target(root, link['href']).is_file():
                link.decompose()
        for img in page.find_all('img'):
            img.attrs.pop("srcset", None)
            src = img.get('src', '')
            target = local_target(root, src)
            if not src or (src.startswith(PREFIX) and (not target or not target.is_file())):
                img.decompose()
        for meta in page.select('meta[name="robots"]'):
            meta.decompose()
        for old_css in page.select('link[href="/mirror/dr-snapshot.css"]'):
            old_css.decompose()
        page.head.append(soup('<meta name="robots" content="noindex, nofollow"><link rel="stylesheet" href="/mirror/dr-snapshot.css">'))
        nav = soup('''<div class="dr-banner"><strong>TEST / DR</strong><span>Tallennettu sivusto · tiedot eivät päivity reaaliajassa</span>
          <a href="/mirror/palvelun-tila/">Miten tämä toimii?</a></div>
          <header class="dr-header"><a class="dr-brand" href="/mirror/">Mielenosoitukset.fi<span>Yhdessä näkyväksi.</span></a>
          <nav aria-label="Päävalikko"><a href="/mirror/">Etusivu</a><a href="/mirror/demonstrations/">Tapahtumat</a>
          <a href="/mirror/cities/">Kaupungit</a><a href="/mirror/ohjeet/">Ohjeet</a><a href="/mirror/contact/">Yhteystiedot</a></nav></header>''')
        page.body.insert(0, nav)
        page.body.append(soup('''<footer class="dr-footer"><strong>Mielenosoitukset.fi</strong><p>Tallennettu SNAPSHOT_DATE · TEST / DR</p>
          <nav aria-label="Alavalikko"><a href="/mirror/info/">Tietoa sivustosta</a><a href="/mirror/privacy/">Tietosuoja</a>
          <a href="/mirror/palvelun-tila/">Tallennetun sivuston toiminta</a></nav></footer>'''.replace('SNAPSHOT_DATE', snapshot_date)))
        path.write_text(str(page))
    (root / 'dr-snapshot.css').write_text(Path(stylesheet).read_text())
    # Remove invalid placeholder imports left by the original crawler.
    for css in root.rglob('*.css'):
        css.write_text(re.sub(r'@import\s+url\(["\x27]?#dr-unavailable["\x27]?\);?', '', css.read_text(errors='replace')))
    report = {"pages_finished": len(pages), "events": len(events), "redirect_stubs_replaced": redirects,
              "unavailable_links_explained": repaired, "requires_backend": False, "snapshot_captured_at": captured.isoformat()}
    (root / 'dr-polish-report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('public_response', type=Path)
    args = parser.parse_args()
    print(json.dumps(polish(args.root, json.loads(args.public_response.read_text()), Path(__file__).with_name('snapshot.css'))))
