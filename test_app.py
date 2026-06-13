"""
Tests for the URL shortening service.
Run with:  python test_app.py
"""

import json
import os
import sys
import tempfile
import unittest

# Point the app at a temp database so tests don't pollute production data
os.environ["TESTING"] = "1"

import app as application

application.DB_PATH = tempfile.mktemp(suffix=".db")
application.init_db()

client = application.app.test_client()


def j(response):
    """Parse JSON from a Flask test response."""
    return json.loads(response.data)


class TestShorten(unittest.TestCase):

    # ── Happy paths ────────────────────────────────────────────

    def test_shorten_returns_short_url(self):
        r = client.post("/api/shorten",
                        json={"url": "https://example.com/some/long/path"})
        self.assertEqual(r.status_code, 201)
        data = j(r)
        self.assertIn("short_url", data)
        self.assertIn("slug", data)
        self.assertEqual(data["original"], "https://example.com/some/long/path")
        self.assertFalse(data["reused"])

    def test_same_url_returns_same_slug(self):
        url = "https://repeat.example.com/"
        r1 = client.post("/api/shorten", json={"url": url})
        r2 = client.post("/api/shorten", json={"url": url})
        self.assertEqual(j(r1)["slug"], j(r2)["slug"])
        self.assertTrue(j(r2)["reused"])

    def test_custom_slug(self):
        r = client.post("/api/shorten",
                        json={"url": "https://custom.example.com/", "custom_slug": "mylink"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(j(r)["slug"], "mylink")

    def test_custom_slug_conflict(self):
        client.post("/api/shorten",
                    json={"url": "https://a.example.com/", "custom_slug": "taken"})
        r = client.post("/api/shorten",
                        json={"url": "https://b.example.com/", "custom_slug": "taken"})
        self.assertEqual(r.status_code, 409)
        self.assertIn("taken", j(r)["error"])

    # ── Validation ─────────────────────────────────────────────

    def test_missing_url(self):
        r = client.post("/api/shorten", json={})
        self.assertEqual(r.status_code, 400)

    def test_invalid_url_no_scheme(self):
        r = client.post("/api/shorten", json={"url": "example.com"})
        self.assertEqual(r.status_code, 400)

    def test_invalid_url_ftp(self):
        # Only http/https accepted
        r = client.post("/api/shorten", json={"url": "ftp://files.example.com/"})
        self.assertEqual(r.status_code, 400)

    def test_invalid_custom_slug_too_short(self):
        r = client.post("/api/shorten",
                        json={"url": "https://ok.example.com/", "custom_slug": "x"})
        self.assertEqual(r.status_code, 400)

    def test_invalid_custom_slug_spaces(self):
        r = client.post("/api/shorten",
                        json={"url": "https://ok.example.com/", "custom_slug": "bad slug"})
        self.assertEqual(r.status_code, 400)


class TestRedirect(unittest.TestCase):

    def setUp(self):
        r = client.post("/api/shorten",
                        json={"url": "https://redirect-target.example.com/"})
        self.slug = j(r)["slug"]

    def test_redirect_returns_302(self):
        r = client.get(f"/{self.slug}", follow_redirects=False)
        self.assertEqual(r.status_code, 302)
        self.assertIn("redirect-target.example.com", r.headers["Location"])

    def test_redirect_increments_clicks(self):
        client.get(f"/{self.slug}", follow_redirects=False)
        client.get(f"/{self.slug}", follow_redirects=False)
        lookup = j(client.get(f"/api/lookup/{self.slug}"))
        self.assertGreaterEqual(lookup["clicks"], 2)

    def test_unknown_slug_404(self):
        r = client.get("/no-such-slug-xyz", follow_redirects=False)
        self.assertEqual(r.status_code, 404)


class TestLookup(unittest.TestCase):

    def setUp(self):
        r = client.post("/api/shorten",
                        json={"url": "https://lookup-test.example.com/"})
        self.slug = j(r)["slug"]

    def test_lookup_returns_original(self):
        r = client.get(f"/api/lookup/{self.slug}")
        self.assertEqual(r.status_code, 200)
        data = j(r)
        self.assertEqual(data["original"], "https://lookup-test.example.com/")
        self.assertIn("clicks", data)
        self.assertIn("created", data)

    def test_lookup_unknown(self):
        r = client.get("/api/lookup/doesnotexist")
        self.assertEqual(r.status_code, 404)


class TestStats(unittest.TestCase):

    def test_stats_returns_list(self):
        r = client.get("/api/stats")
        self.assertEqual(r.status_code, 200)
        data = j(r)
        self.assertIsInstance(data, list)
        if data:
            self.assertIn("slug", data[0])
            self.assertIn("clicks", data[0])


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    # Clean up temp db
    try:
        os.unlink(application.DB_PATH)
    except OSError:
        pass
    sys.exit(0 if result.wasSuccessful() else 1)
