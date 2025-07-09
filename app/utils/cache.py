from cachetools import TTLCache

player_search_cache = TTLCache(maxsize=1000, ttl=3600)
player_profile_cache = TTLCache(maxsize=1000, ttl=3600)
player_transfers_cache = TTLCache(maxsize=1000, ttl=3600)
player_injuries_cache = TTLCache(maxsize=1000, ttl=3600)
player_stats_cache = TTLCache(maxsize=1000, ttl=3600)

club_search_cache = TTLCache(maxsize=1000, ttl=3600)
club_profile_cache = TTLCache(maxsize=1000, ttl=3600)
club_squad_cache = TTLCache(maxsize=1000, ttl=3600)
club_transfers_cache = TTLCache(maxsize=1000, ttl=3600)
club_fixtures_cache = TTLCache(maxsize=1000, ttl=3600)

leagues_search_cache = TTLCache(maxsize=1000, ttl=3600)
leagues_top_scorers_cache = TTLCache(maxsize=1000, ttl=3600)
leagues_clubs_cache = TTLCache(maxsize=1000, ttl=3600)
leagues_transfers_overview_cache = TTLCache(maxsize=1000, ttl=3600)
leagues_table_cache = TTLCache(maxsize=1000, ttl=3600)

staff_search_cache =  TTLCache(maxsize=1000, ttl=3600)
staff_profile_cache = TTLCache(maxsize=1000, ttl=3600)