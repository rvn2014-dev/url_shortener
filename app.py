"""
URL Shortening Service
A Flask-based URL shortener with SQLite persistence.
"""

import sqlite3
import string
import random
import re
from datetime import datetime
from flask import Flask, request, jsonify, redirect, render_template, abort

app = Flask(__name__)
DB_PATH = "urls.db"

# ── Database ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                slug      TEXT    NOT NULL UNIQUE,
                original  TEXT    NOT NULL,
                clicks    INTEGER NOT NULL DEFAULT 0,
                created   TEXT    NOT NULL
            )
        """)
        conn.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

ALPHABET = string.ascii_letters + string.digits   # 62 chars

def generate_slug(length: int = 6) -> str:
    return "".join(random.choices(ALPHABET, k=length))


def is_valid_url(url: str) -> bool:
    pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(pattern.match(url))


def get_base_url() -> str:
    return request.host_url.rstrip("/")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/shorten", methods=["POST"])
def shorten():
    """Create a shortened URL.

    Body (JSON): { "url": "https://...", "custom_slug": "optional" }
    Returns:     { "short_url": "...", "slug": "...", "original": "..." }
    """
    data = request.get_json(silent=True) or {}
    original = (data.get("url") or "").strip()
    custom   = (data.get("custom_slug") or "").strip()

    if not original:
        return jsonify(error="URL is required."), 400
    if not is_valid_url(original):
        return jsonify(error="Please enter a valid URL (must start with http:// or https://)."), 400

    with get_db() as conn:
        # Re-use existing slug if same URL was already shortened
        row = conn.execute(
            "SELECT slug FROM urls WHERE original = ?", (original,)
        ).fetchone()
        if row and not custom:
            slug = row["slug"]
            return jsonify(
                short_url=f"{get_base_url()}/{slug}",
                slug=slug,
                original=original,
                reused=True,
            )

        # Validate or generate slug
        if custom:
            if not re.match(r"^[A-Za-z0-9_-]{2,32}$", custom):
                return jsonify(
                    error="Custom slug must be 2–32 characters: letters, digits, - or _."
                ), 400
            if conn.execute("SELECT 1 FROM urls WHERE slug = ?", (custom,)).fetchone():
                return jsonify(error=f"'{custom}' is already taken. Try another."), 409
            slug = custom
        else:
            for _ in range(10):          # up to 10 attempts to find unique slug
                candidate = generate_slug()
                if not conn.execute(
                    "SELECT 1 FROM urls WHERE slug = ?", (candidate,)
                ).fetchone():
                    slug = candidate
                    break
            else:
                return jsonify(error="Could not generate a unique slug. Try again."), 500

        conn.execute(
            "INSERT INTO urls (slug, original, created) VALUES (?, ?, ?)",
            (slug, original, datetime.utcnow().isoformat()),
        )
        conn.commit()

    return jsonify(
        short_url=f"{get_base_url()}/{slug}",
        slug=slug,
        original=original,
        reused=False,
    ), 201


@app.route("/api/lookup/<slug>")
def lookup(slug: str):
    """Return the original URL for a slug (JSON, no redirect)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT original, clicks, created FROM urls WHERE slug = ?", (slug,)
        ).fetchone()
    if not row:
        return jsonify(error="Short URL not found."), 404
    return jsonify(
        slug=slug,
        original=row["original"],
        clicks=row["clicks"],
        created=row["created"],
    )


@app.route("/api/stats")
def stats():
    """Return the 20 most-clicked links."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT slug, original, clicks, created FROM urls ORDER BY clicks DESC LIMIT 20"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/<slug>")
def redirect_to_url(slug: str):
    """Redirect to the original URL and increment click count."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT original FROM urls WHERE slug = ?", (slug,)
        ).fetchone()
        if not row:
            abort(404)
        conn.execute("UPDATE urls SET clicks = clicks + 1 WHERE slug = ?", (slug,))
        conn.commit()
    return redirect(row["original"], code=302)


# ── 404 handler ───────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify(error="Not found."), 404
    return render_template("index.html"), 404   # SPA fallback


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("✓ Database ready")
    print("✓ Server starting at http://localhost:5000")
    app.run(debug=True, port=5000)
