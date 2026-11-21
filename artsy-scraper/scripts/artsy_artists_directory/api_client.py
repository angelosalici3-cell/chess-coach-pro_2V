"""
Artsy A-Z Artists Directory API Client
=======================================
Fetches the complete list of artists from Artsy's public API,
paginating through all artists in the A-Z artists directory.

API: https://api.artsy.net/api/v1/artists
Auth: X-Xapp-Token (application-level JWT, refreshed from artsy.net)

Fields per artist:
  - name: Artist display name
  - slug: URL slug (the `id` field in the API)
  - nationality: Nationality string
  - birthday: Birth year string
  - deathday: Death year string (empty/None if alive)
  - profile_url: https://www.artsy.net/artist/{slug}
"""

from __future__ import annotations

import json
import math
import re
import time
from typing import Iterator

import requests

# ---------------------------------------------------------------------------
# Auth — XAPP token (valid ~6 days from creation; auto-refreshes from artsy.net)
# ---------------------------------------------------------------------------
_XAPP_TOKEN = ""  # fetched at runtime from artsy.net (public app token, expires ~7 days)

API_BASE = "https://api.artsy.net/api/v1"
ARTSY_BASE = "https://www.artsy.net"
PAGE_SIZE = 100  # maximum allowed by the API


def fetch_fresh_xapp_token(session: requests.Session) -> str:
    """Fetch a fresh XAPP token by extracting it from the Artsy homepage SSR data."""
    resp = session.get(
        f"{ARTSY_BASE}/artists",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
        },
        timeout=30,
    )
    resp.raise_for_status()
    # The page embeds __sharifyData JSON in the HTML
    match = re.search(r"window\.__sharifyData\s*=\s*'({.*?})'", resp.text)
    if not match:
        # Try without escaping (sometimes the value is a plain JSON object)
        match = re.search(r"__sharifyData\s*=\s*(\{[^\n]+ARTSY_XAPP_TOKEN[^\n]+\})", resp.text)
    if match:
        try:
            sharify = json.loads(match.group(1))
            token = sharify.get("ARTSY_XAPP_TOKEN", "")
            if token:
                return token
        except json.JSONDecodeError:
            pass
    raise RuntimeError("Could not extract XAPP token from artsy.net HTML")


def _xapp_expired(token: str) -> bool:
    """Return True if the JWT XAPP token has expired (or is within 60 s of expiry)."""
    try:
        # JWT: header.payload.signature (base64url-encoded)
        parts = token.split(".")
        if len(parts) != 3:
            return True
        # Pad base64url payload
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        import base64
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp", 0)
        return time.time() > exp - 60
    except Exception:
        return True


class ArtsyArtistsClient:
    """Client for the Artsy artists REST API."""

    def __init__(self, xapp_token: str = _XAPP_TOKEN, delay: float = 0.35) -> None:
        self.delay = delay
        self.session = requests.Session()
        self._token = xapp_token
        # Set common headers
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
            }
        )

    def _get_token(self) -> str:
        """Return a valid XAPP token, refreshing if necessary."""
        if _xapp_expired(self._token):
            print("XAPP token expired, fetching fresh token…")
            self._token = fetch_fresh_xapp_token(self.session)
            print("Token refreshed.")
        return self._token

    def _get_artists_page(self, page: int, size: int = PAGE_SIZE) -> tuple[list[dict], int]:
        """
        Fetch a single page of artists from the REST API.

        Returns:
            (artists_list, total_count)
        """
        for attempt in range(5):
            try:
                return self._get_artists_page_once(page, size)
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status is not None and status < 500 and status != 429:
                    raise
                wait = 2 ** attempt
                print(f"  page {page}: {e!r}, retry in {wait}s", flush=True)
                time.sleep(wait)
        return self._get_artists_page_once(page, size)

    def _get_artists_page_once(self, page: int, size: int = PAGE_SIZE) -> tuple[list[dict], int]:
        time.sleep(self.delay)
        token = self._get_token()
        resp = self.session.get(
            f"{API_BASE}/artists",
            params={
                "size": size,
                "page": page,
                "total_count": 1,  # ask for X-Total-Count header
            },
            headers={"X-Xapp-Token": token},
            timeout=30,
        )

        if resp.status_code == 401 or resp.status_code == 403:
            # Token may have been invalidated server-side; refresh and retry once
            print(f"Auth error ({resp.status_code}), refreshing token…")
            self._token = fetch_fresh_xapp_token(self.session)
            resp = self.session.get(
                f"{API_BASE}/artists",
                params={"size": size, "page": page, "total_count": 1},
                headers={"X-Xapp-Token": self._token},
                timeout=30,
            )

        resp.raise_for_status()
        total = int(resp.headers.get("X-Total-Count", 0))
        artists = resp.json()
        if not isinstance(artists, list):
            raise ValueError(f"Unexpected response: {str(artists)[:200]}")
        return artists, total

    # Set of ASCII uppercase letters for A-Z filtering
    _AZ_LETTERS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    # Regex to detect MongoDB ObjectId-style slugs (24-char hex) which indicate
    # artists without a proper human-readable slug
    _OBJECTID_RE = re.compile(r'^[0-9a-f]{24}$')

    def _is_az_artist(self, name: str, slug: str) -> bool:
        """Return True if the artist belongs in the standard A-Z web directory."""
        if not name or not slug:
            return False
        # Skip entries with MongoDB ObjectID-style slugs (not human-readable)
        if self._OBJECTID_RE.match(slug):
            return False
        # Only keep artists whose name starts with an ASCII letter A-Z
        return name[0].upper() in self._AZ_LETTERS

    def iter_all_artists(
        self, start_page: int = 1, az_only: bool = True
    ) -> Iterator[dict]:
        """
        Iterate over ALL artists in the directory.

        Args:
            start_page: Page to start from (1-indexed). Useful for resuming.
            az_only:    If True (default), yield only artists whose name
                        begins with A–Z (matching the web's A-Z artists directory).
                        Excludes entries with numeric/symbol prefixes, Unicode
                        non-ASCII letter prefixes, and MongoDB ObjectID slugs.

        Yields:
            Dicts with keys: name, slug, nationality, birthday, deathday, profile_url
        """
        # Fetch first page to get total
        page = start_page
        artists_page, total = self._get_artists_page(page)
        total_pages = math.ceil(total / PAGE_SIZE)
        print(f"Total artists in API: {total:,} → {total_pages:,} pages of {PAGE_SIZE}")

        while True:
            for raw in artists_page:
                slug = raw.get("id") or ""
                name = raw.get("name") or ""
                # Skip entries without a valid slug
                if not slug or slug == "artist":
                    continue
                # Skip non-A-Z entries if requested
                if az_only and not self._is_az_artist(name, slug):
                    continue
                yield {
                    "name": name,
                    "slug": slug,
                    "nationality": raw.get("nationality") or "",
                    "birthday": raw.get("birthday") or "",
                    "deathday": raw.get("deathday") or "",
                    "profile_url": f"{ARTSY_BASE}/artist/{slug}",
                }

            if page >= total_pages:
                break
            page += 1
            artists_page, _ = self._get_artists_page(page)

    def get_artists_by_letter(self, letter: str) -> Iterator[dict]:
        """
        Iterate over artists whose name starts with the given letter (A–Z).

        Note: The REST API does not support server-side letter filtering.
        This method pages through ALL artists and filters client-side.
        For efficiency when scraping a single letter, prefer iter_all_artists()
        and filter the results yourself.

        Args:
            letter: Single uppercase or lowercase letter (e.g. "A").
        """
        letter = letter.upper()
        for artist in self.iter_all_artists(az_only=False):
            first = (artist["name"] or " ")[0].upper()
            if first == letter:
                yield artist

    def get_total_count(self) -> int:
        """Return the total number of public artists in the API."""
        _, total = self._get_artists_page(1, size=1)
        return total


def main() -> None:
    """Stream all artists to a JSONL file.

    Usage: python3 api_client.py [output.jsonl] [--az-only]
    """
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Download all Artsy artists to JSONL")
    ap.add_argument("output", nargs="?", default="artists.jsonl")
    ap.add_argument("--az-only", action="store_true",
                    help="keep only names starting with A-Z and readable slugs")
    ap.add_argument("--start-page", type=int, default=1)
    args = ap.parse_args()

    client = ArtsyArtistsClient()
    mode = "a" if args.start_page > 1 else "w"
    count = 0
    try:
        with open(args.output, mode, encoding="utf-8") as fh:
            for artist in client.iter_all_artists(start_page=args.start_page, az_only=args.az_only):
                fh.write(json.dumps(artist, ensure_ascii=False) + "\n")
                count += 1
                if count % 5000 == 0:
                    print(f"  {count:,} artists written", flush=True)
    except KeyboardInterrupt:
        print(f"\nStopped early. {count:,} artists written.")
        sys.exit(1)
    print(f"Done. {count:,} artists written to {args.output}")


if __name__ == "__main__":
    main()
