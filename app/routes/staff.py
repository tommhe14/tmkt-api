from fastapi import APIRouter, HTTPException

from ..utils.scraping import search_club_staff, get_staff_profile_scraping
from ..utils.cache import staff_search_cache, staff_profile_cache

router = APIRouter()

@router.get("/search")
async def search_staff(query: str):
    try:
        search = await search_club_staff(query)
        return {"query": query, "results": search, "cache_hit": query in staff_search_cache}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("{staff_id}/profile")
async def get_staff_profile(staff_id: str):
    try:
        profile = await get_staff_profile_scraping(staff_id)
        return {"query": staff_id, "result": profile, "cache_hit": staff_id in staff_profile_cache}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

