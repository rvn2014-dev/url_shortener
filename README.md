# snip. — URL Shortener

A clean, fast URL shortening service built with Python (Flask) and SQLite.

```
POST /api/shorten  →  { short_url, slug, original }
GET  /<slug>       →  302 redirect to original URL
GET  /api/lookup/<slug>  →  { slug, original, clicks, created }
GET  /api/stats          →  top 20 links by clicks
```

---

## Quick start

```bash
git clone https://github.com/rvn2014-dev/url_shortener.git
cd url_shortener/urlshort

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install flask

python app.py
# → http://localhost:5000
```

---

## HTTP API

### Shorten a URL

```
POST /api/shorten
Content-Type: application/json

{ "url": "https://open.gov.sg/", "custom_slug": "optional" }
```

**Responses**

| Status | Meaning |
|--------|---------|
| `201 Created` | New short URL created |
| `200 OK` | URL was already shortened (returns existing slug) |
| `400 Bad Request` | Missing or invalid URL / slug |
| `409 Conflict` | Custom slug already taken |

```json
{
  "short_url": "http://localhost:5000/aB3kLz",
  "slug": "aB3kLz",
  "original": "https://open.gov.sg/",
  "reused": false
}
```

### Redirect

```
GET /<slug>
→ 302  Location: <original URL>
```

Click count is incremented on every redirect.

### Lookup (no redirect)

```
GET /api/lookup/<slug>
```

```json
{
  "slug": "aB3kLz",
  "original": "https://open.gov.sg/",
  "clicks": 42,
  "created": "2024-01-15T10:30:00"
}
```

### Top links

```
GET /api/stats
→ [ { slug, original, clicks, created }, … ]   (top 20 by clicks)
```

---

## Running tests

```bash
python test_app.py
```

16 tests covering: URL validation, slug generation, deduplication, custom slugs, conflict detection, redirects, click counting, and stats.

---

## Project structure

```
urlshort/
├── app.py          # Flask application + routes
├── test_app.py     # Unit & functional tests
├── templates/
│   └── index.html  # Single-page frontend
└── README.md
```

SQLite database (`urls.db`) is created automatically in the working directory on first run.

---

## Deployment

### Fly.io (recommended — free tier)

```bash
pip install flyctl
fly launch          # follow prompts, pick a region
fly deploy
```

Add a `fly.toml`:

```toml
[build]
  [build.args]
    PYTHON_VERSION = "3.12"

[[services]]
  internal_port = 8080
  protocol = "tcp"
  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]
```

Use a volume for the SQLite file:

```toml
[[mounts]]
  source = "data"
  destination = "/data"
```

And update `DB_PATH = "/data/urls.db"` in `app.py`.

### Railway

```bash
# Add a Procfile:
echo "web: gunicorn app:app" > Procfile
pip install gunicorn
# Push repo → Railway auto-deploys
```

### Self-hosted (systemd)

```ini
# /etc/systemd/system/snip.service
[Unit]
Description=snip URL shortener
After=network.target

[Service]
WorkingDirectory=/opt/snip
ExecStart=/opt/snip/.venv/bin/gunicorn -w 2 -b 0.0.0.0:8080 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now snip
```

---

## Extensions implemented

- **Styling** — Dark terminal-aesthetic UI (`JetBrains Mono`), responsive layout, custom-slug toggle, copy-to-clipboard, live stats table.
- **DB Setup** — SQLite persistence via Python's built-in `sqlite3`; zero extra dependencies.
- **Testing** — 16 unit/functional tests in `test_app.py`.

---

## Design decisions

- **No external DB dependency** — SQLite ships with Python, making the service trivially deployable anywhere.
- **Slug deduplication** — Shortening the same URL twice returns the existing slug (idempotent), keeping the database tidy.
- **Custom slugs** — Validated as `[A-Za-z0-9_-]{2,32}`; conflicts return `409` with a clear error.
- **Click tracking** — Every redirect atomically increments a counter; the stats endpoint surfaces the most-visited links.
