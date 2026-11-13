#!/usr/bin/env bash
# Create the application-owned virtual environment used by Gunicorn and by
# deploy/production_deploy.sh. Run once as root on the production host:
#
#   deploy/create_production_venv.sh [VENV_DIR]
#
# The venv sees the system site-packages (Gunicorn, eventlet and other packages
# outside requirements.txt keep working) but the pins in requirements.txt are
# installed inside the venv and win over the system copies. The system Python is
# never modified, so pointing the service back at /usr/bin/python3 is the
# rollback. Idempotent: an existing venv is reused.
set -euo pipefail

venv=${1:-/opt/mielenosoitukset-fi/venv}
base_python=${BASE_PYTHON:-/usr/bin/python3}

[[ $(id -u) -eq 0 ]] || { echo "create_production_venv.sh: run as root" >&2; exit 2; }
[[ $venv == /* ]] || { echo "create_production_venv.sh: VENV_DIR must be absolute" >&2; exit 2; }

mkdir -p "$(dirname "$venv")"
[[ -x $venv/bin/python ]] || "$base_python" -m venv --system-site-packages "$venv"
# Root owns the environment; the www-data workers only read and execute it.
chown -R root:root "$venv"
chmod -R go-w "$venv"
echo "venv ready: $venv"
