#!/usr/bin/env python3
"""Preserve the serving site's Cloudflare peer ACL for the new API vhost."""
from pathlib import Path

source = Path('/etc/apache2/sites-enabled/mielenosoitukset-le-ssl.conf').read_text()
start = source.index('<Location "/">')
end = source.index('</Location>', start) + len('</Location>')
restriction = source[start:end]
if 'CONN_REMOTE_ADDR' not in restriction or '<RequireAny>' not in restriction:
    raise SystemExit('Expected production Cloudflare peer restriction missing')
Path('/etc/mielenosoitukset-api/cloudflare-origin.conf').write_text(restriction + '\n')
print('Copied existing Cloudflare peer restriction; no origin bypass added')
