from fastapi import APIRouter, HTTPException, Request
from ..utils.rate_limiter import rate_limiter

from app.utils.scraping import scrape_todays_matches

from datetime import datetime

router = APIRouter()

@router.get("/today")
async def get_todays_matches(request: Request):
    client_ip = request.client.host
    
    await rate_limiter.check_rate_limit(
        key=f"search_clubs:{client_ip}", 
        limit=5, 
        window=60 
    )
    try:
        matches = await scrape_todays_matches()
        return {"query": "/today", "results": matches, "cache_hit": False}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error scraping matches: {str(e)}"
        )
    
@router.get("/date/{date}")
async def get_matches_by_date(request: Request, date: str):
    """
    Get matches for a specific date (format: YYYY-MM-DD)
    Example: /matches/date/2025-07-07
    """
    client_ip = request.client.host
    
    await rate_limiter.check_rate_limit(
        key=f"search_clubs:{client_ip}", 
        limit=5, 
        window=60 
    )

    try:
        datetime.strptime(date, "%Y-%m-%d")
        matches = await scrape_todays_matches(date)
        return {"query": date, "results": matches, "cache_hit": False}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))