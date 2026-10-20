#!/usr/bin/env python3
"""Reject broken local navigation/assets before publishing a static release."""
import argparse
import hashlib
import json
from pathlib import Path

from polish_snapshot import local_target, soup


def verify(root):
    root = Path(root).resolve()
    errors = []
    pages = links = assets = 0
    for path in root.rglob('*'):
        if path.is_symlink() or path.name == '.env' or path.name.startswith('.env.'):
            errors.append('Forbidden snapshot member: ' + str(path.relative_to(root)))
        if path.suffix != '.html':
            continue
        pages += 1
        page = soup(path.read_text(encoding='utf-8'))
        if page.select('script, form, iframe, object'):
            errors.append('Active content in ' + str(path.relative_to(root)))
        if len(page.select('nav[aria-label="Päävalikko"]')) != 1:
            errors.append('Missing or duplicate navigation: ' + str(path.relative_to(root)))
        if not page.select_one('meta[name="robots"][content="noindex, nofollow"]'):
            errors.append('Missing noindex: ' + str(path.relative_to(root)))
        for node in page.select('[href], [src]'):
            value = node.get('href') or node.get('src') or ''
            if value.startswith('/mirror/'):
                if node.name == 'a':
                    links += 1
                else:
                    assets += 1
                target = local_target(root, value)
                if not target or not target.is_file():
                    errors.append('Missing local resource: ' + value)
    for required in ['index.html', 'demonstrations/index.html', 'cities/index.html',
                     'contact/index.html', 'palvelun-tila/index.html', 'dr-snapshot.css']:
        if not (root / required).is_file():
            errors.append('Missing required page/asset: ' + required)
    if errors:
        raise ValueError('; '.join(errors[:20]))
    return {'pages': pages, 'local_links': links, 'local_assets': assets, 'broken_resources': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--write-manifest', action='store_true')
    args = parser.parse_args()
    result = verify(args.root)
    if args.write_manifest:
        hashes = {str(p.relative_to(args.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(args.root.rglob('*')) if p.is_file() and p.name != 'dr-integrity.json'}
        (args.root / 'dr-integrity.json').write_text(json.dumps(hashes, indent=2) + '\n')
    print(json.dumps(result))
