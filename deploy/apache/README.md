# Apache production error response

`rate-limit.html` is a static, application-independent response for Apache
`mod_evasive` blocks. Install it outside the application checkout so a blocked
response never depends on Flask or the current deploy state:

```bash
install -d -o root -g www-data -m 0755 /var/www/mielenosoitukset-error-pages
install -o root -g www-data -m 0644 deploy/apache/rate-limit.html \
  /var/www/mielenosoitukset-error-pages/rate-limit.html
```

Then add the directives from
`mielenosoitukset-rate-limit-vhost.conf` to the production TLS virtual host
before its catch-all `ProxyPass "/"` rule, then run:

```bash
apache2ctl configtest
systemctl reload apache2
```

The production host must also keep `mod_remoteip` ahead of `mod_evasive` and
trust only Cloudflare's published proxy ranges. The mod_evasive log directory
must be owned and writable by Apache's runtime user; on Debian/Ubuntu:

```bash
install -d -o www-data -g www-data -m 0750 /var/log/apache2/mod_evasive
```

Do not enable `ProxyErrorOverride`: application authorization responses must
continue to come from Flask. Do not test the block by flooding the public
hostname; use a controlled staging client and confirm the original response
status remains 403 with `Retry-After: 60`.
