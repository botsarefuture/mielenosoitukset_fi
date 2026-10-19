#!/bin/bash
# Switch only this sandbox's root URL. /mirror/ always remains static.
set -euo pipefail
test "$(hostname)" = mielenosoitukset-pentest
case "${1:-}" in
  app) systemctl is-active --quiet dr-app; target=/etc/nginx/snippets/dr-app.conf ;;
  snapshot) test -s /srv/dr-snapshots/prepared/index.html; target=/etc/nginx/snippets/dr-snapshot.conf ;;
  *) echo 'Usage: switch_mode.sh {app|snapshot}' >&2; exit 2 ;;
esac
previous=$(readlink /etc/nginx/snippets/dr-active.conf)
ln -s "$target" /etc/nginx/snippets/dr-active.next
mv -Tf /etc/nginx/snippets/dr-active.next /etc/nginx/snippets/dr-active.conf
if nginx -t; then
    systemctl reload nginx
else
    ln -s "$previous" /etc/nginx/snippets/dr-active.next
    mv -Tf /etc/nginx/snippets/dr-active.next /etc/nginx/snippets/dr-active.conf
    exit 1
fi
