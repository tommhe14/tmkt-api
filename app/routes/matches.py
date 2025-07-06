from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.utils.scraping import scrape_todays_matches
from datetime import datetime

router = APIRouter()

@router.get("/today")
async def get_todays_matches():
    try:
        matches = await scrape_todays_matches()
        return JSONResponse(content=matches)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error scraping matches: {str(e)}"
        )
    
@router.get("/date/{date}")
async def get_matches_by_date(date: str):
    """
    Get matches for a specific date (format: YYYY-MM-DD)
    Example: /matches/date/2025-07-07
    """
    try:
        datetime.strptime(date, "%Y-%m-%d")
        matches = await scrape_todays_matches(date)
        return JSONResponse(content=matches)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))