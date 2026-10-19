#!/usr/bin/env python3
"""Materialize a bounded public event response; serve no API from the mirror.

Input must come from the anonymous GET /api/demonstrations endpoint used by the
public event list. No accounts, contact messages or authenticated data belong here.
"""
import argparse
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import quote

from prepare_snapshot import Mirror, SOURCE, StaticHTML


def materialize(root, public_response):
    events = public_response["results"][:24]
    mirror = Mirror(root)
    cards = []
    for event in events:
        raw = str(event.get("slug") or event.get("running_number") or event["_id"])
        if raw in {"", ".", ".."} or "/" in raw or "\\" in raw:
            raise ValueError("unsafe event identifier")
        identifier = quote(raw, safe="")
        rel = "demonstration/" + raw + "/index.html"
        path = root / rel
        if not path.exists():
            result = subprocess.run(["curl", "--fail", "--silent", "--show-error",
                                     "--max-time", "25", "--proto", "=https",
                                     SOURCE + "/demonstration/" + identifier], capture_output=True, check=True)
            # Canonical redirect bodies are not event content. Require a heading.
            if b"<h1" not in result.stdout:
                raise RuntimeError("Event URL did not return event HTML")
            parser = StaticHTML(mirror, SOURCE + "/demonstration/" + identifier)
            parser.feed(result.stdout.decode())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(parser.output))
            time.sleep(0.2)
        title = escape(str(event.get("title", "")))
        details = " · ".join(escape(str(event.get(key) or "")) for key in
                             ["formatted_date", "start_time", "city", "address"])
        cards.append('<article style="padding:20px;border:1px solid #ddd;border-radius:12px">'
                     f'<h3><a href="/mirror/demonstration/{identifier}/">{title}</a></h3>'
                     f'<p>{details}</p></article>')
    block = ('<section id="dr-public-events" style="padding:24px">'
             '<h2>Tulevat mielenosoitukset — tallennettu näkymä</h2>'
             '<p>Staattinen otos julkisesta tapahtumalistasta. Ei reaaliaikaisia päivityksiä.</p>'
             + "".join(cards) + "</section>")
    for rel in ["index.html", "demonstrations/index.html"]:
        path = root / rel
        html = path.read_text()
        html = re.sub(r'<section id="dr-public-events".*?</section>', "", html, flags=re.S)
        html = html.replace("</main>", block + "</main>", 1)
        path.write_text(html)
    report = {"events_materialized": len(events), "source_total": public_response.get("total"),
              "captured_at": datetime.now(timezone.utc).isoformat(),
              "scope": "First public page only; not the full event archive"}
    (root / "dr-events-report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("public_response", type=Path)
    args = parser.parse_args()
    materialize(args.root, json.loads(args.public_response.read_text()))
