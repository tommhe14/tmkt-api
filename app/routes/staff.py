from fastapi import APIRouter, HTTPException, Request

from ..utils.scraping import search_club_staff, get_staff_profile_scraping
from ..utils.cache import staff_search_cache, staff_profile_cache
from ..utils.rate_limiter import rate_limiter

router = APIRouter()

@router.get("/search")
async def search_staff(request: Request, query: str):
    client_ip = request.client.host
    
    await rate_limiter.check_rate_limit(
        key=f"search_staff:{client_ip}", 
        limit=5, 
        window=60 
    )
    try:
        search = await search_club_staff(query)
        return {"query": query, "results": search, "cache_hit": query in staff_search_cache}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("{staff_id}/profile")
async def get_staff_profile(request: Request, staff_id: str):
    client_ip = request.client.host
    
    await rate_limiter.check_rate_limit(
        key=f"staff_profile:{client_ip}", 
        limit=5, 
        window=60 
    )
    try:
        profile = await get_staff_profile_scraping(staff_id)
        return {"query": staff_id, "result": profile, "cache_hit": staff_id in staff_profile_cache}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

