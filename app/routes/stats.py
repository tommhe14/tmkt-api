from fastapi import APIRouter, HTTPException, Request

from ..utils.scraping import get_foreign_players_request
from ..utils.cache import foreign_players_cache
from ..utils.rate_limiter import rate_limiter
from ..utils.store.management import get_country_list

router = APIRouter()

@router.get("/countries")
async def get_countries(request: Request):
    client_ip = request.client.host
    
    await rate_limiter.check_rate_limit(
        key=f"countries:{client_ip}", 
        limit=5, 
        window=60 
    )
    try:
        countries = await get_country_list()
        return countries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/foreign_players")
async def get_current_foreign_players(request: Request, country_id: int):
    """
    Get list of countries and number of players from specified country playing abroad
    """
    client_ip = request.client.host
    
    await rate_limiter.check_rate_limit(
        key=f"foreign_players:{client_ip}", 
        limit=5, 
        window=60 
    )
    try:
        countries = await get_foreign_players_request(country_id)
        return {"query": country_id, "results": countries, "cache_hit": country_id in foreign_players_cache}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
