# Artsy A-Z Artists Directory API Client

Fetches the complete list of artists from Artsy's public REST API, paginating through all artists that appear in the A-Z artists directory at https://www.artsy.net/artists.

## APIs Discovered

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `https://api.artsy.net/api/v1/artists` | GET | List all public artists (paginated) |
| `https://www.artsy.net/artists` | GET | Extract fresh XAPP token from SSR HTML |

### Artist List Endpoint

```
GET https://api.artsy.net/api/v1/artists
  ?size=100       # max page size
  &page=1         # 1-indexed
  &total_count=1  # enables X-Total-Count response header
```

**Response:** JSON array of artist objects  
**Pagination:** `X-Total-Count` header gives the total. Total ≈ 321,183 artists → 3,212 pages.

### Artist Object Fields Used

| Field | Description |
|-------|-------------|
| `id` | Artist slug (URL-safe string, e.g. `pablo-picasso`) |
| `name` | Display name |
| `nationality` | Nationality string (may be empty) |
| `birthday` | Birth year string (may be empty) |
| `deathday` | Death year string (None or empty if alive) |
| `sortable_id` | Last-first sort key used by the API's default ordering |

## Authentication

The API uses an **application-level XAPP token** (JWT) passed as the `X-Xapp-Token` header.  
Tokens are valid for approximately **7 days** and are embedded in every SSR HTML page served by artsy.net (inside `window.__sharifyData.ARTSY_XAPP_TOKEN`).

The client auto-refreshes the token when it expires:
1. Checks JWT `exp` claim before each request  
2. On expiry (or 401/403), fetches `https://www.artsy.net/artists`, parses `__sharifyData` from the HTML, and extracts a fresh token

**No user login is required** — the XAPP token is a public application credential.

## Sort Order

The API sorts by `sortable_id` (lastname-firstname), not by display name. Artists with empty `sortable_id` (e.g. special-character names) appear first. The web's A-Z directory sorts by first letter of `name`.

## Filtering (A-Z Directory)

The API does not support server-side letter filtering. The `letter=` parameter is ignored. The client filters client-side:
- Keeps only artists whose `name` starts with an ASCII letter A–Z
- Skips artists with MongoDB ObjectID-style slugs (24-char hex) which lack a human-readable profile URL

## Usage

### Run the full crawler

```bash
python3 api_client.py
```

This writes one JSONL record per artist to `artists.jsonl`:

```json
{"name": "Pablo Picasso", "slug": "pablo-picasso", "nationality": "Spanish", "birthday": "1881", "deathday": "1973", "profile_url": "https://www.artsy.net/artist/pablo-picasso"}
```

Press **Ctrl-C** to stop early; progress is printed every 1,000 artists.

### Use as a library

```python
from api_client import ArtsyArtistsClient

client = ArtsyArtistsClient()

# Count total
print(client.get_total_count())  # ~321,183

# Stream all A-Z artists
for artist in client.iter_all_artists(az_only=True):
    print(artist["name"], artist["nationality"])

# Stream a single letter
for artist in client.get_artists_by_letter("P"):
    print(artist["name"], artist["slug"])
```

### Resume from a specific page

```python
# Resume from page 500
for artist in client.iter_all_artists(start_page=500):
    ...
```

## Caveats

- **Rate limits:** No explicit rate limit was observed during testing, but the API is a production endpoint — keep requests at a reasonable pace (~2–3 req/s).
- **Token expiry:** The hardcoded token is valid for ~7 days from the date it was captured. The auto-refresh fetches a new token from `www.artsy.net`.
- **Completeness:** The REST API returns all *public* artists. The web's A-Z directory (via GraphQL at `metaphysics-cdn.artsy.net/v2`) may show a slightly different subset. The difference is small and in practice the two match closely.
- **Empty nationality/birthday:** Many artists have empty `nationality`, `birthday`, and `deathday` fields — this reflects the actual state of Artsy's database, not a scraping gap.
- **Full crawl time:** At 100 artists/request and ~3,212 pages, a full crawl takes approximately 15–20 minutes depending on network conditions.
