"""HTTP helpers shared by the download runner and the source registry."""

import json
import time
import urllib.error
import urllib.request

# ISBE and nj.gov reset connections from requests without browser-like headers.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}
RETRIES = 3       # attempts per request before giving up on a network error
CHUNK = 1 << 20   # bytes read per block when streaming or hashing (1 MiB)


def open_url(url, timeout=120):
    """Open url with retries on network errors. HTTP errors are raised immediately."""
    for attempt in range(1, RETRIES + 1):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS),
                                          timeout=timeout)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == RETRIES:
                raise
            print(f"    retry {attempt}/{RETRIES - 1} after {type(e).__name__}: {e}")
            # Back off longer after each failure (5 s, then 10 s).
            time.sleep(5 * attempt)


def get_json(url):
    """Fetch url and parse the response body as JSON."""
    with open_url(url) as r:
        return json.load(r)


def get_text(url):
    """Fetch url and return the body as text, using the server's charset (UTF-8 if none)."""
    with open_url(url) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", errors="replace")
