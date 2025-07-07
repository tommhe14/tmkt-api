from fastapi import APIRouter, Request

from ..utils.scraping import scrape_transfers
from ..utils.rate_limiter import rate_limiter

router = APIRouter()

@router.get("/")
async def get_transfers(request: Request):
    client_ip = request.client.host
    
    await rate_limiter.check_rate_limit(
        key=f"search_clubs:{client_ip}", 
        limit=5, 
        window=60 
    )

    transfers = await scrape_transfers()
    return {"query":"transfers", "results": transfers, "cache_hit": False}