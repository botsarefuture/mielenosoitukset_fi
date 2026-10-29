#!/usr/bin/env bash
set -euo pipefail
[[ ${RENEWED_LINEAGE:-} == /etc/letsencrypt/live/api.mielenosoitukset.fi ]] || exit 0
/usr/sbin/apache2ctl configtest
/bin/systemctl reload apache2
