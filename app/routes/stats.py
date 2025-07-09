from fastapi import APIRouter, HTTPException, Request

from ..utils.scraping import get_country_list, get_foreign_players_request
from ..utils.cache import country_list_cache, foreign_players_cache
from ..utils.rate_limiter import rate_limiter

router = APIRouter()

@router.get("/countries")
async def get_countries(request: Request, query: str):
    client_ip = request.client.host
    
    await rate_limiter.check_rate_limit(
        key=f"search_clubs:{client_ip}", 
        limit=5, 
        window=60 
    )
    try:
        countries = await get_country_list(query)
        return {"query": query, "results": countries, "cache_hit": query in country_list_cache}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/foreign_players")
async def get_current_foreign_players(request: Request, country_id: int):
    """
    Get list of countries and number of players from specified country playing abroad
    """
    client_ip = request.client.host
    
    await rate_limiter.check_rate_limit(
        key=f"search_clubs:{client_ip}", 
        limit=5, 
        window=60 
    )
    try:
        countries = await get_foreign_players_request(country_id)
        return {"query": country_id, "results": countries, "cache_hit": country_id in foreign_players_cache}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))