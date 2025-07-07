from fastapi import APIRouter, HTTPException

from ..utils.scraping import fetch_transfermarkt_players, scrape_player_profile, scrape_player_stats, get_player_transfers
from ..utils.cache import player_search_cache, player_profile_cache, player_injuries_cache, player_stats_cache, player_transfers_cache

router = APIRouter()

@router.get("/search")
async def search_players(query: str):
    """
    Search for players on Transfermarkt
    
    Parameters:
    - query: str - Player name to search for
    
    Returns:
    - List of players with id, name, and current team
    """
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters long")
    
    try:
        players = await fetch_transfermarkt_players(query)
        return {
            "query": query,
            "results": players,
            "cache_hit": query in player_search_cache
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/{player_id}")
async def get_player_profile(player_id: str):
    """
    Get detailed profile for a specific player by ID
    Example: /players/433177 (for Bukayo Saka)
    """
    try:
        if not player_id.isdigit():
            raise HTTPException(status_code=400, detail="Player ID must be numeric")
        
        profile = await scrape_player_profile(player_id)
        return {
            "query": player_id,
            "results": profile,
            "cache_hit": player_id in player_profile_cache
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/{player_id}/stats")
async def get_player_stats(
    player_id: str,
    season: str = None 
):
    """
    Get player statistics for a specific season or all-time
    
    Parameters:
    - player_id: Transfermarkt player ID
    - season: (optional) Season year in format YYYY (e.g. 2024)
    
    Returns:
    - JSON object containing total stats and competition breakdown
    """
    try:
        stats = await scrape_player_stats(player_id, season)
        return {"query": player_id, "results": stats, "cache_hit": (player_id, season) in player_stats_cache}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching player stats: {str(e)}"
        )
    
@router.get("/{player_id}/transfers")
async def get_player_transfers_request(
    player_id: str
):
    try:
        data = await get_player_transfers(player_id)
        return {"query": player_id, "results": data, "cache_hit": player_id in player_transfers_cache}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching player transfers: {str(e)}"
        )
    
@router.get("/{player_id}/injuries")
async def get_player_injuries(
    player_id: str
):
    try:
        data = await get_player_transfers(player_id)
        return {"query": player_id, "results": data, "cache_hit": player_id in player_injuries_cache}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching player transfers: {str(e)}"
        )