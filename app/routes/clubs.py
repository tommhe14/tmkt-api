from fastapi import APIRouter, HTTPException

from ..utils.scraping import fetch_transfermarkt_clubs, scrape_club_profile, scrape_club_squad, scrape_transfers
from ..utils.cache import club_search_cache, club_profile_cache, club_squad_cache, club_transfers_cache

from datetime import datetime

router = APIRouter()

@router.get("/search")
async def search_clubs(query: str):
    """
    Search for clubs on Transfermarkt
    
    Parameters:
    - query: str - Club name to search for
    
    Returns:
    - List of clubs with id, name, and market value
    """
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters long")
    
    try:
        clubs = await fetch_transfermarkt_clubs(query)
        return {
            "query": query,
            "results": clubs,
            "cache_hit": query in club_search_cache
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/{club_id}")
async def get_club_profile(
    club_id: str
):
    try:
        data = await scrape_club_profile(club_id)
        return {"query": club_id, "data": data, "cache_hit": club_id in club_profile_cache}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error Returning Club Profile: {str(e)}"
        )
    
@router.get("/{club_id}/squad")
async def get_club_squad(club_id: int):
    """
    Get detailed squad information for a club from Transfermarkt
    
    Parameters:
    - club_id: Transfermarkt club ID (e.g., 11 for Arsenal)
    
    Returns:
    - List of players with their details
    """
    try:
        squad_data = await scrape_club_squad(str(club_id))
        return {
            "query": club_id,
            "result": squad_data,
            "cache_hit":club_id in club_squad_cache
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/{team_id}/transfers")
async def get_team_transfers(
    team_id: int,
    season: int
):
    """
    Get transfer history for a team by ID and season
    
    Parameters:
    - team_id: Transfermarkt team ID (e.g., 11 for Arsenal)
    - season: Season year (default: 2024)
    
    Returns:
    - List of transfers with player details
    """
    try:
        # Set cache headers
        
        # Call scraping function with team_id and season
        transfers = await scrape_transfers(team_id, season)
        
        return {
            "query": team_id,
            "season": season,
            "results": transfers,
            "cache_hit": (team_id, season) in club_transfers_cache
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))