"""
Fetch and cache anime start_date data from the MyAnimeList API.
Provides a lookup interface with automatic 48-hour cache refresh.
"""

import json
import os
import time
from datetime import datetime, timedelta

import requests


class MALDateLookup:
    """Local cache + lookup for MAL anime start dates."""

    API_URL = "https://api.myanimelist.net/v2/anime/ranking"
    CLIENT_ID = os.environ.get("MAL_CLIENT_ID")
    LIMIT = 500
    DEFAULT_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mal_dates_cache.json")
    DEFAULT_MAX_AGE = timedelta(hours=48)

    def __init__(self, cache_path=None, max_age=None):
        self._cache_path = cache_path or self.DEFAULT_CACHE_PATH
        self._max_age = max_age or self.DEFAULT_MAX_AGE
        self._headers = {"X-MAL-CLIENT-ID": self.CLIENT_ID}
        self._entries = {}  # mal_id (int) -> start_date (str)
        self._load_or_refresh()

    # ── public API ──────────────────────────────────────────────

    def lookup(self, mal_id: int) -> str | None:
        """Return the start_date for a MAL ID, or None if not found."""
        return self._entries.get(int(mal_id))

    def refresh(self, force: bool = False):
        """Re-fetch from the API if the cache is stale (or if *force* is True)."""
        if force or self._is_stale():
            self._fetch_all()
            self._save_cache()

    @property
    def size(self) -> int:
        return len(self._entries)

    # ── internals ───────────────────────────────────────────────

    def _load_or_refresh(self):
        if os.path.exists(self._cache_path) and not self._is_stale():
            self._load_cache()
            print(f"[MALDateLookup] Loaded {len(self._entries)} entries from cache.")
        else:
            print("[MALDateLookup] Cache missing or stale -- fetching from API...")
            self._fetch_all()
            self._save_cache()

    def _is_stale(self) -> bool:
        if not os.path.exists(self._cache_path):
            return True
        mtime = datetime.fromtimestamp(os.path.getmtime(self._cache_path))
        return datetime.now() - mtime > self._max_age

    def _fetch_all(self):
        entries = {}
        offset = 0
        while True:
            params = {
                "ranking_type": "all",
                "limit": self.LIMIT,
                "offset": offset,
                "fields": "start_date",
            }
            print(f"  Fetching offset {offset}...")
            resp = requests.get(self.API_URL, headers=self._headers, params=params)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("data", []):
                node = item["node"]
                entries[node["id"]] = node.get("start_date", "unknown")

            if data.get("paging", {}).get("next"):
                offset += self.LIMIT
                time.sleep(0.5)
            else:
                break

        self._entries = entries
        print(f"  Fetched {len(entries)} entries total.")

    def _save_cache(self):
        # Store as JSON: {"fetched": iso-timestamp, "entries": {id: date, ...}}
        payload = {
            "fetched": datetime.now().isoformat(),
            "entries": {str(k): v for k, v in self._entries.items()},
        }
        with open(self._cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        print(f"[MALDateLookup] Cache saved to {self._cache_path}")

    def _load_cache(self):
        with open(self._cache_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        self._entries = {int(k): v for k, v in payload["entries"].items()}


# ── standalone usage ────────────────────────────────────────────

if __name__ == "__main__":
    lookup = MALDateLookup()
    lookup.refresh(force=True)
    print(f"\nTotal entries: {lookup.size}")

    # Quick demo lookup
    test_id = 63147
    print(f"MAL {test_id} -> {lookup.lookup(test_id)}")
