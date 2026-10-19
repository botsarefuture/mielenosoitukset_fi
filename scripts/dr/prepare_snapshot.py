#!/usr/bin/env python3
"""Make the existing public crawler's output a read-only, self-contained mirror.

Run on a machine allowed to read the public site, before uploading the result.
Never use an authenticated browser session. This does not copy application data.
"""
import argparse
import json
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urljoin, urlsplit

SOURCE = "https://mielenosoitukset.fi"
ASSET_HOSTS = {"mielenosoitukset.fi", "cdn2.mielenosoitukset.fi"}
BLOCKED = re.compile(r"^/(admin|api|users|login|logout|register|submit|suggest|notifications|profile|account|mcp|developer)(/|$)")
CSS_URL = re.compile(r"url\(\s*['\"]?([^)'\"\s]+)['\"]?\s*\)")


def destination(url):
    parsed = urlsplit(url)
    parts = Path(parsed.path).parts
    if ".." in parts or "%2e" in parsed.path.lower() or "%2f" in parsed.path.lower():
        raise ValueError("unsafe asset path")
    path = parsed.path.lstrip("/")
    if not path or path.endswith("/"):
        path += "index.html"
    if parsed.hostname != "mielenosoitukset.fi":
        path = "_external/" + parsed.hostname + "/" + path
    return path


class Mirror:
    def __init__(self, root, prefix="/mirror/"):
        self.root = Path(root)
        self.prefix = prefix
        self.processed = set()
        self.failures = []
        self.missing_images = []

    def link(self, value, base, asset=False):
        if value.startswith(("#", "data:", "mailto:", "tel:", self.prefix)):
            return value
        url = urljoin(base, value)
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            return "#dr-unavailable"
        if parsed.hostname not in ASSET_HOSTS:
            return "#dr-unavailable" if asset else value
        if BLOCKED.search(parsed.path) or parsed.path.startswith("/cdn-cgi/"):
            return "#dr-unavailable"
        rel = destination(url)
        if asset:
            if self.asset(url, rel) is False:
                return self.prefix + "dr-missing-image.svg"
        elif parsed.hostname == "mielenosoitukset.fi":
            candidate = self.root / rel
            if not candidate.is_file() and not Path(parsed.path).suffix:
                candidate = self.root / parsed.path.lstrip("/") / "index.html"
            if not candidate.is_file():
                return "#dr-unavailable"
            rel = parsed.path.lstrip("/")
        return self.prefix + rel + ("#" + parsed.fragment if parsed.fragment else "")

    def asset(self, url, rel):
        if rel in self.processed:
            return (self.root / rel).exists()
        if len(self.processed) >= 2500:
            raise RuntimeError("asset limit reached")
        self.processed.add(rel)
        path = self.root / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["curl", "--fail", "--silent", "--show-error", "--max-time", "25",
                 "--max-filesize", "20971520", "--proto", "=https", "-o", str(path), url],
                capture_output=True,
            )
            time.sleep(0.2)
            if result.returncode:
                path.unlink(missing_ok=True)
                if path.suffix.lower() in {".css", ".woff", ".woff2", ".ttf", ".otf"}:
                    self.failures.append(url)
                else:
                    self.missing_images.append(url)
                return False
        if path.suffix.lower() == ".css":
            content = path.read_text(errors="replace")
            content = CSS_URL.sub(lambda m: "url(\"" + self.link(m[1], url, True) + "\")", content)
            path.write_text(content)
        return True

    def run(self):
        for path in list(self.root.rglob("*.html")):
            rel = path.relative_to(self.root).as_posix()
            base = SOURCE + "/" + rel.removesuffix("index.html")
            parser = StaticHTML(self, base)
            parser.feed(path.read_text(errors="replace"))
            path.write_text("".join(parser.output))
        (self.root / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
        (self.root / "dr-missing-image.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">'
            '<rect width="640" height="360" fill="#eee"/>'
            '<text x="30" y="180" font-size="22">Image unavailable in DR snapshot</text></svg>')
        (self.root / "dr-snapshot-report.json").write_text(json.dumps({
            "html_pages": len(list(self.root.rglob("*.html"))),
            "assets_checked": len(self.processed),
            "missing_images": self.missing_images,
            "missing_required_assets": self.failures,
        }, indent=2) + "\n")
        if self.failures:
            raise RuntimeError("Missing public assets: " + ", ".join(self.failures[:20]))


class StaticHTML(HTMLParser):
    def __init__(self, mirror, base):
        super().__init__(convert_charrefs=False)
        self.mirror, self.base = mirror, base
        self.output = []
        self.hidden = []
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "form", "iframe", "object"}:
            self.hidden.append(tag)
        if self.hidden:
            return
        values = dict(attrs)
        if tag == "style":
            self.in_style = True
        if tag == "base" or (tag == "meta" and values.get("http-equiv", "").lower() == "refresh"):
            return
        if tag == "link" and not set(values.get("rel", "").lower().split()).intersection({"stylesheet", "icon"}):
            return
        if tag in {"button", "input", "textarea", "select"}:
            return
        output = []
        for key, value in attrs:
            if key.startswith("on") or key in {"integrity", "nonce"}:
                continue
            if key in {"href", "src", "poster"} and value:
                value = self.mirror.link(value, self.base, asset=(key != "href" or tag == "link"))
            if key == "srcset" and value:
                value = ", ".join(self.mirror.link(item.strip().split()[0], self.base, True)
                                  + " " + " ".join(item.strip().split()[1:]) for item in value.split(","))
            if key == "style" and value:
                value = CSS_URL.sub(lambda m: "url('" + self.mirror.link(m[1], self.base, True) + "')", value)
            output.append(key if value is None else key + '="' + escape(value, quote=True) + '"')
        self.output.append("<" + tag + (" " if output else "") + " ".join(output) + ">")
        if tag == "body":
            self.output.append('<aside style="background:#ffe08a;color:#111;padding:16px;font:16px sans-serif">'
                               'TEST / DR SNAPSHOT — read-only copy. Forms and scripts are disabled. '
                               'This is not the live service.</aside>')

    def handle_endtag(self, tag):
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if tag == "style":
            self.in_style = False
        if tag not in {"button", "textarea", "select"}:
            self.output.append("</" + tag + ">")

    def handle_data(self, data):
        if not self.hidden:
            if self.in_style:
                data = CSS_URL.sub(lambda m: 'url("' + self.mirror.link(m[1], self.base, True) + '")', data)
            self.output.append(data)

    def handle_entityref(self, name):
        self.handle_data("&" + name + ";")

    def handle_charref(self, name):
        self.handle_data("&#" + name + ";")

    def handle_decl(self, decl):
        self.output.append("<!" + decl + ">")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    Mirror(args.root).run()
