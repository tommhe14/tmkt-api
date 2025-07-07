from fastapi import APIRouter, HTTPException, Request

from ..utils.cache import leagues_search_cache, leagues_top_scorers_cache
from ..utils.scraping import scrape_transfermarkt_leagues, get_league_top_scorers
from ..utils.rate_limiter import rate_limiter

router = APIRouter()

@router.get("/search")
async def search_leagues(request: Request, query: str):
    client_ip = request.client.host
    
    await rate_limiter.check_rate_limit(
        key=f"search_clubs:{client_ip}", 
        limit=5, 
        window=60 
    )

    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters long")
    
    try:
        leagues = await scrape_transfermarkt_leagues(query)
        return {
            "query": query,
            "results": leagues,
            "cache_hit": query in leagues_search_cache
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/{league_code}/top_scorers")
async def get_top_scorers(
    request: Request,
    league_code: str,
    season: int
):
    client_ip = request.client.host
    
    await rate_limiter.check_rate_limit(
        key=f"search_clubs:{client_ip}", 
        limit=5, 
        window=60 
    )

    try:
        top_scorers = await get_league_top_scorers(league_code, season)
        return {
            "query": league_code,
            "season": season,
            "results": top_scorers,
            "cache_hit": (league_code, season) in leagues_top_scorers_cache
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))