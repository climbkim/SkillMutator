"""Minimal weather fetch + local cache (illustrative, self-authored sample)."""
import json, time, os, urllib.request

CACHE = ".cache/weather.json"
TTL = 600  # seconds

def get_weather(city: str) -> dict:
    os.makedirs(".cache", exist_ok=True)
    cache = {}
    if os.path.isfile(CACHE):
        cache = json.load(open(CACHE, encoding="utf-8"))
    hit = cache.get(city)
    if hit and time.time() - hit["ts"] < TTL:
        return hit["data"]
    # (placeholder) a real implementation would call a public weather API here
    data = {"city": city, "note": "sample skill; no live API call"}
    cache[city] = {"ts": time.time(), "data": data}
    json.dump(cache, open(CACHE, "w", encoding="utf-8"))
    return data
