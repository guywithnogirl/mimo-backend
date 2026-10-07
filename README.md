# Private Chat Backend

Django REST API for a private conversation between exactly two configured accounts. The production layout uses Nginx, Gunicorn with the supported Uvicorn worker package, Django ASGI, and PostgreSQL. The API currently provides JWT authentication and a database-backed health endpoint. Channels, WebSockets, messages, FCM, and media are not implemented yet.

## Local setup

From this directory:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=true`, `AUTHORIZED_USERNAMES` to exactly two distinct account names, and `DATABASE_URL`. Then:

```sh
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

The JWT endpoints are `POST /api/auth/token/` and `POST /api/auth/token/refresh/`. `GET /api/auth/me/` requires a valid access token. `GET /api/health/` checks database connectivity and returns only `ok` or `unavailable`. There is no registration API. Create the two intended users through Django administration.

## Production architecture

```text
Internet → Nginx (HTTPS, static files, HTTP/WebSocket proxy)
         → Gunicorn + Uvicorn worker (127.0.0.1:8000, Django ASGI)
         → PostgreSQL (127.0.0.1:5432)
```

The application port and PostgreSQL are loopback-only. Nginx uses `deploy/nginx-upgrade-map.conf` for WebSocket upgrade headers. The `/ws/` proxy route is ready for a future Channels phase; this backend does not currently implement a WebSocket consumer, so no WebSocket functionality should be considered deployed or verified.

## Oracle VM setup

The deployment target is Ubuntu 22.04 at `/opt/our-app/backend`; the backend repo is deployed separately from the Android repository. Required system packages are Python 3 venv support, PostgreSQL, Nginx, Git, and CA certificates. Run OS package updates and installs through `apt`, not system-wide `pip`.

Create a dedicated `privatechat` service account and a PostgreSQL database and login role named `privatechat`. Generate a strong random database password and Django secret; never reuse the Ubuntu account password. Keep the database listening on localhost only. Store production settings in `/etc/our-app/backend.env`, owned by `root:privatechat` with mode `0640`. Do not put this file in Git.

Required environment variables:

| Name | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Random Django signing secret |
| `DJANGO_DEBUG` | `false` in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames, no scheme |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins |
| `DJANGO_STATIC_ROOT` | Production collected-static directory |
| `AUTHORIZED_USERNAMES` | Exactly two distinct account names |
| `DATABASE_URL` | PostgreSQL connection URL using the app role |

FCM and object-storage variables are not needed until those features are implemented. `config/settings.py` rejects missing or duplicate authorized names and rejects a missing secret when debug is off.

## PostgreSQL

Use the local PostgreSQL cluster and a dedicated database role. For an installation, generate a password with a cryptographically secure random generator, create the application role/database as the `postgres` OS account, and place the password only in the root-managed environment file. Verify the configured connection as the application role before migrating:

```sh
sudo -u postgres psql -c '\du'
sudo -u postgres psql -c '\l'
/opt/our-app/backend/.venv/bin/python -m django check --deploy
```

The first two commands are inspection examples; do not recreate an existing database or role without checking it first. Use `psql "$DATABASE_URL" -c 'SELECT 1'` from a protected environment to verify database access without printing the password.

## Application service

The systemd template is `deploy/privatechat.service`. Install it as `/etc/systemd/system/privatechat.service`, create `/etc/our-app/backend.env`, then:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now privatechat
sudo systemctl status privatechat
sudo journalctl -u privatechat -n 100 --no-pager
```

The service runs as the unprivileged `privatechat` user, loads secrets through `EnvironmentFile`, serves ASGI through one Gunicorn worker, and binds only to `127.0.0.1:8000`. Django management commands also load `/etc/our-app/backend.env`; the service account must be able to read it.

## Nginx and HTTPS

The domain must resolve to the VM, and the Oracle network security list/NSG must permit inbound TCP 80 and 443. Do not open PostgreSQL or port 8000 publicly. The firewall should retain SSH access on 22. Inspect Oracle cloud ingress rules as well as the host firewall.

Before DNS is ready, `deploy/nginx-acme-only.conf` can serve only ACME challenges and returns 404 for other HTTP paths. After DNS resolves correctly, install Certbot and its Nginx plugin, obtain a Let's Encrypt certificate using the webroot or Nginx method, install `deploy/nginx-upgrade-map.conf` under `/etc/nginx/conf.d/`, then install `deploy/nginx-site.conf` under `/etc/nginx/sites-available/` and enable the site. The site redirects HTTP to HTTPS, serves collected static files, and forwards REST and future WebSocket traffic. Validate before applying:

```sh
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl reload nginx
sudo certbot renew --dry-run
```

Do not install the TLS site template until the certificate files exist. Verify HTTP redirects to HTTPS and certificate validation succeeds before enabling HSTS for users.

## Django checks and account setup

```sh
cd /opt/our-app/backend
sudo -u privatechat /opt/our-app/backend/.venv/bin/python manage.py check
sudo -u privatechat /opt/our-app/backend/.venv/bin/python manage.py check --deploy
sudo -u privatechat /opt/our-app/backend/.venv/bin/python manage.py migrate
sudo -u privatechat /opt/our-app/backend/.venv/bin/python manage.py collectstatic --noinput
sudo -u privatechat /opt/our-app/backend/.venv/bin/python manage.py test accounts
```

Create the two authorized user accounts after the usernames are chosen. Use Django's password prompts or another secure interactive method. No public registration endpoint exists. Verify both users can obtain tokens and an unrelated account cannot.

For the initial VM bootstrap, randomly generated passwords for the two authorized users are held outside Git in `/etc/our-app/bootstrap-credentials.txt` (root-owned, mode `0600`). Retrieve them only over SSH with `sudo cat /etc/our-app/bootstrap-credentials.txt`; keep them private. After saving them securely, rotate each through the interactive Django `changepassword` command and remove the bootstrap file.

The current `check --deploy` output has two intentional warnings: `security.W005` because HSTS is not applied to subdomains, and `security.W021` because this DuckDNS hostname is not configured for browser preload. Leave both disabled unless the hostname's future subdomain and preload policy are explicitly reviewed.

## Deploy/update and rollback

Run deployment commands as the deployment owner from `/opt/our-app/backend`:

```sh
git pull --ff-only
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py check --deploy
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart privatechat
curl --fail https://buvimaaa.duckdns.org/api/health/
sudo journalctl -u privatechat -n 100 --no-pager
```

Before deploying, note the current commit with `git rev-parse HEAD`. Roll back code with `git switch --detach <previous-commit>`, reinstall that revision's requirements, run its compatible migrations, collect static files, restart the service, and verify health. Database migrations may not be reversible; take a PostgreSQL backup before migrations and restore it only when an explicitly approved rollback requires it.

## Diagnostics

```sh
sudo systemctl status privatechat nginx postgresql
sudo journalctl -u privatechat -f
sudo journalctl -u nginx -n 100 --no-pager
sudo nginx -t
sudo ss -ltn
pg_isready
curl --fail https://buvimaaa.duckdns.org/api/health/
```

No tokens, passwords, database URLs, private keys, or message bodies should be written to logs. Do not claim REST/HTTPS/WebSocket verification until each check has actually been performed.
