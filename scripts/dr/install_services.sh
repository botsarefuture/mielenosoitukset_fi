#!/bin/bash
# Run only on the already-provisioned pentest host after installing Python,
# Redis and verified /usr/local/bin/{mongod,mailpit,minio} binaries.
# Does not start the application or database before backup extraction.
set -euo pipefail
test "$(hostname)" = mielenosoitukset-pentest
test "$(id -u)" = 0
for binary in /usr/local/bin/mongod /usr/local/bin/mailpit /usr/local/bin/minio; do
    test -x "$binary"
done
id dr-app >/dev/null 2>&1 || useradd --system --home-dir /srv/mielenosoitukset-dr --shell /usr/sbin/nologin dr-app
id dr-mail >/dev/null 2>&1 || useradd --system --home-dir /var/lib/dr-mailpit --shell /usr/sbin/nologin dr-mail
id dr-db >/dev/null 2>&1 || useradd --system --home-dir /srv/mielenosoitukset-dr/mongodb --shell /usr/sbin/nologin dr-db
install -d -m 750 -o dr-mail -g dr-mail /var/lib/dr-mailpit
install -d -m 750 -o dr-db -g dr-db /srv/mielenosoitukset-dr/mongodb
install -d -m 755 /srv/mielenosoitukset-dr
install -d -m 750 -o dr-app -g dr-app /var/lib/dr-minio
chown dr-app:dr-app /etc/mielenosoitukset-dr/config.yaml
chmod 600 /etc/mielenosoitukset-dr/config.yaml
chmod 711 /etc/mielenosoitukset-dr

cat > /etc/systemd/system/dr-mailpit.service <<'UNIT'
[Unit]
Description=DR mail capture (no relay or forwarding)
After=network.target
[Service]
User=dr-mail
Group=dr-mail
ExecStart=/usr/local/bin/mailpit --database /var/lib/dr-mailpit/messages.db --listen 127.0.0.1:8025 --smtp 127.0.0.1:1025 --disable-version-check --smtp-disable-rdns --smtp-auth-accept-any --smtp-auth-allow-insecure --max 5000 --label "TEST / DR - capture only"
Restart=on-failure
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/dr-mailpit
IPAddressDeny=any
IPAddressAllow=localhost
[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/dr-mongodb.service <<'UNIT'
[Unit]
Description=DR MongoDB 7.0.37 restored from logical backup
After=network.target
[Service]
User=dr-db
Group=dr-db
ExecStart=/usr/local/bin/mongod --dbpath /srv/mielenosoitukset-dr/mongodb --bind_ip 127.0.0.1 --port 27017 --wiredTigerCacheSizeGB 0.5
Restart=on-failure
TimeoutStopSec=180
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/mielenosoitukset-dr/mongodb
IPAddressDeny=any
IPAddressAllow=localhost
[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/dr-s3.service <<'UNIT'
[Unit]
Description=DR isolated MinIO object storage (loopback only)
After=network.target
[Service]
User=dr-app
Group=dr-app
EnvironmentFile=/etc/mielenosoitukset-dr/minio.env
ExecStart=/usr/local/bin/minio server --address 127.0.0.1:5003 --console-address 127.0.0.1:5005 /var/lib/dr-minio
Restart=on-failure
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/dr-minio
IPAddressDeny=any
IPAddressAllow=localhost
[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/dr-app.service <<'UNIT'
[Unit]
Description=Mielenosoitukset pentest / DR restored application
After=network.target dr-mongodb.service redis-server.service dr-mailpit.service dr-s3.service
Requires=dr-mongodb.service dr-mailpit.service dr-s3.service
[Service]
User=dr-app
Group=dr-app
WorkingDirectory=/srv/mielenosoitukset-dr/app
Environment=CONFIG_YAML_PATH=/etc/mielenosoitukset-dr/config.yaml
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=AWS_EC2_METADATA_DISABLED=true
Environment=PYTHONPATH=/srv/mielenosoitukset-dr/app:/srv/mielenosoitukset-dr/app/mielenosoitukset_fi:/srv/mielenosoitukset-dr
ExecStart=/srv/mielenosoitukset-dr/venv/bin/gunicorn -k eventlet --workers 1 --bind 127.0.0.1:5002 --timeout 90 sandbox_wsgi:app
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/srv/mielenosoitukset-dr/app
IPAddressDeny=any
IPAddressAllow=localhost
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now dr-mailpit dr-s3
systemctl enable dr-mongodb dr-app
