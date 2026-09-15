---
name: weather-cache
description: Cache recent weather lookups locally to avoid repeated API calls.
version: 1.0.0
license: MIT
---

# Weather Cache

Fetch the current weather for a city and cache the result locally for 10 minutes
so repeated lookups do not hit the upstream API again.

## Usage
Call `get_weather(city)`. Cached entries are stored in `.cache/weather.json`
and expire after 10 minutes.

## Files
- `scripts/fetch.py` - fetch from the public weather API and refresh the cache.
