# Moving production Flask to an application virtual environment

Production Flask, its workers and the deploy script run on the distro's system
Python (`/usr/bin/python3`, Ubuntu 24.04, Python 3.12). `deploy/install_dependencies.py`
treats that environment as read-only, so a pin change in `requirements.txt` stops
every deploy until the application has its own virtual environment. #1053 (Pillow,
PyJWT and PyMongo security update) hit this on 10 November 2026 and was reverted
by #1056.

This runbook creates that environment and moves every production Python process
onto it. It is a production infrastructure change: run it only with the
maintainer's go-ahead, as root on the production host, in a quiet hour. Expect a
few seconds of 503 on Flask-served pages while Gunicorn restarts in step 6; the
React host and Go API keep serving.

Paths used below:

| What | Path |
| --- | --- |
| Checkout | `/var/www/mielenosoitukset_fi` |
| New venv | `/opt/mielenosoitukset-fi/venv` |
| Deploy settings | `/etc/mielenosoitukset-fi/deploy.env` |
| New install record | `/var/lib/mielenosoitukset-fi-deploy/dependencies-venv.json` |
| Old install record (kept) | `/var/lib/mielenosoitukset-fi-deploy/dependencies.json` |

Take the deploy lock for the whole procedure so no deploy runs in between:

```sh
exec 9>/run/lock/mielenosoitukset-fi-deploy.lock && flock -w 300 9
```

## 1. Inventory every Python process (read only)

Record the output in the change log for rollback.

```sh
systemctl cat mielenosoitukset_fi
systemctl list-units --type=service --all | grep -i -E 'mielenosoitukset|moso|aggregate|worker|python'
grep -rl -E 'python3?|gunicorn' /etc/systemd/system /lib/systemd/system 2>/dev/null | xargs -r grep -l -E 'mielenosoitukset|moso' 2>/dev/null
crontab -l; ls /etc/cron.d; grep -rl mielenosoitukset /etc/cron* 2>/dev/null
ps -eo user,pid,cmd | grep -E 'python|gunicorn' | grep -v grep
/usr/bin/python3 -m pip freeze > /root/system-python-freeze-$(date +%F).txt
/usr/bin/python3 -m pip show gunicorn | grep -E '^(Name|Version)'
cat /var/www/mielenosoitukset_fi/.deploy-build-sha
```

Note for each unit or cron entry: its `ExecStart` or command line, its user, and
whether it imports the application. Also note Gunicorn's worker class (for
example `-k eventlet` or `-k gevent`) and that package's version from the freeze,
because neither Gunicorn nor its worker package is pinned in `requirements.txt`.

`systemd` units known from the repository: `mielenosoitukset_fi` (Gunicorn),
`mielenosoitukset-public` (Node, unaffected), `mielenosoitukset-api` (Go,
unaffected) and the analytics rollup `.setups/anal_aggregate.service`, which runs
`/usr/bin/python3 -u .../run_aggregate.py` and must move too if it is installed.

## 2. Create the venv and install the manifest

```sh
apt-get install -y python3-venv          # only if `python3 -m venv` is missing
install -d -o root -g root -m 0755 /opt/mielenosoitukset-fi
python3 -m venv /opt/mielenosoitukset-fi/venv
V=/opt/mielenosoitukset-fi/venv/bin/python
bash /var/www/mielenosoitukset_fi/deploy/bootstrap_python_trust.sh "$V"
"$V" -m pip install --disable-pip-version-check --no-cache-dir -r /var/www/mielenosoitukset_fi/requirements.txt
"$V" -m pip install --disable-pip-version-check --no-cache-dir 'gunicorn==<version from step 1>' '<worker package>==<version from step 1>'
"$V" -m pip check
```

The venv stays root-owned and read-only for `www-data`; the services only need to
read and execute it.

**Known drift.** The system environment differs from the pins in five packages,
including Flask 3.1.3 (pin 3.1.1), Flask-Cors 5.0.0 (pin 6.0.0) and boto3/botocore
1.35 (pin 1.42). The venv installs the pinned versions, which are what CI tests.
If you would rather keep a running version, change its pin in a reviewed PR
first, then reinstall.

## 3. Smoke-test the venv as the service user

```sh
cd /var/www/mielenosoitukset_fi
sudo -u www-data /opt/mielenosoitukset-fi/venv/bin/python -c 'import PIL, jwt, pymongo, flask; print("imports ok")'
sudo -u www-data /opt/mielenosoitukset-fi/venv/bin/python -c 'from mielenosoitukset_fi.app import create_app; create_app(); print("app ok")'
```

Use the same user and working directory as the Gunicorn unit if they differ from
`www-data` and the checkout. Stop here on any error; nothing has changed yet.

## 4. Point the deploy script at the venv

```sh
install -d -o root -g root -m 0755 /etc/mielenosoitukset-fi
cat > /etc/mielenosoitukset-fi/deploy.env <<'EOF'
PRODUCTION_PYTHON=/opt/mielenosoitukset-fi/venv/bin/python
PRODUCTION_DEPENDENCY_RECEIPT=/var/lib/mielenosoitukset-fi-deploy/dependencies-venv.json
EOF
chown root:root /etc/mielenosoitukset-fi/deploy.env && chmod 0644 /etc/mielenosoitukset-fi/deploy.env
```

`deploy/production_deploy.sh` parses this file (it never sources it) and accepts
only these two settings; a group- or world-writable file, a symlink or any other
line stops the deploy. A separate install record is required because
`install_dependencies.py` rejects a record written for another interpreter.

## 5. Move the services with systemd drop-ins

For `mielenosoitukset_fi`, copy its current `ExecStart` from step 1 and replace only
the interpreter or Gunicorn path:

```sh
systemctl edit mielenosoitukset_fi
```

```ini
[Service]
ExecStart=
ExecStart=/opt/mielenosoitukset-fi/venv/bin/gunicorn <the same arguments as before>
```

If the original runs `python3 -m gunicorn ...`, use
`/opt/mielenosoitukset-fi/venv/bin/python -m gunicorn ...` instead. Do the same for
every other unit or cron entry from step 1 that imports the application, for
example the analytics rollup:

```ini
[Service]
ExecStart=
ExecStart=/opt/mielenosoitukset-fi/venv/bin/python -u <the same script path as before>
```

Then `systemctl daemon-reload` and check each with `systemctl cat <unit>`.

## 6. Restart and verify

A changed `ExecStart` needs a restart, not the usual graceful reload:

```sh
systemctl restart mielenosoitukset_fi
systemctl is-active mielenosoitukset_fi
tr '\0' ' ' < /proc/$(systemctl show -p MainPID --value mielenosoitukset_fi)/cmdline; echo
/opt/mielenosoitukset-fi/venv/bin/python deploy/verify_health_sha.py --help >/dev/null && echo verifier ok
curl -fsS --unix-socket /var/www/mielenosoitukset_fi/mielenosoitus.sock http://localhost/health
```

Restart the other moved units the same way. Check that the main PID's command line
shows the venv, that `/health` reports the current build, and that Flask-served
pages work: `/users/auth/login`, `/admin/` while signed in, `/kampanja/api/volunteers`
answering a POST with a validation error, and an image upload through the submit
form. Watch `journalctl -u mielenosoitukset_fi -f` for import errors for a few
minutes.

## 7. Let a deploy record the venv

Release the lock (`exec 9>&-`) and re-run the latest Production deploy workflow on
GitHub. With no venv record yet, `install_dependencies.py` verifies the whole
manifest against the venv, installs nothing (step 2 did) and writes
`dependencies-venv.json`. The deploy must end with the usual verified worker
reload.

## 8. Re-apply the security update

Revert #1056 (re-applying #1053). Its deploy now installs only Pillow 13.0.0,
PyJWT 2.15.1 and PyMongo 4.19.0 into the venv, records them and reloads the
workers. Confirm with
`/opt/mielenosoitukset-fi/venv/bin/python -m pip show Pillow PyJWT pymongo`.

## Rollback

At any step the system Python and its install record are untouched.

```sh
rm /etc/mielenosoitukset-fi/deploy.env
systemctl revert mielenosoitukset_fi      # and every other unit given a drop-in
systemctl daemon-reload
systemctl restart mielenosoitukset_fi
```

Restore any changed cron entries from the step 1 record. Deploys then use
`/usr/bin/python3` and `dependencies.json` again; if step 8 already ran, revert
it first, because the system Python still has the old package versions. The venv
in `/opt/mielenosoitukset-fi` can stay for inspection or be removed.
