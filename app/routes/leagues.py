from fastapi import APIRouter, HTTPException

from ..utils.cache import leagues_search_cache
from ..utils.scraping import scrape_transfermarkt_leagues

router = APIRouter()

@router.get("/search")
async def search_leagues(query: str):
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