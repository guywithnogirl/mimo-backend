# Private Chat Backend

Django REST Framework foundation for a private conversation between exactly two configured accounts.

## Local setup

From this directory:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` in this directory and set `DJANGO_SECRET_KEY`, `AUTHORIZED_USERNAMES` to exactly two distinct usernames, and `DATABASE_URL`. The server refuses to start unless both account names are configured. Then:

```sh
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

The JWT endpoints are `POST /api/auth/token/` and `POST /api/auth/token/refresh/`. `GET /api/auth/me/` returns the authenticated identity. There is no registration API. Create exactly the configured user accounts through Django's administrative tooling.

SQLite is the no-setup local default; PostgreSQL is configured using `DATABASE_URL`. Use HTTPS, a strong secret, and `DJANGO_DEBUG=false` in production.

## Phase 1 status

Authentication foundation only. Conversation, message history, Channels, FCM, media, tests, and production deployment are later phases.
