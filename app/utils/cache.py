from cachetools import TTLCache

player_search_cache = TTLCache(maxsize=1000, ttl=3600)
player_profile_cache = TTLCache(maxsize=1000, ttl=3600)
club_search_cache = TTLCache(maxsize=1000, ttl=3600)
player_transfers_cache = TTLCache(maxsize=1000, ttl=3600)
leagues_search_cache = TTLCache(maxsize=1000)