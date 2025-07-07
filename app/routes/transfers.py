from fastapi import APIRouter

from ..utils.scraping import scrape_transfers

router = APIRouter()

@router.get("/")
async def get_transfers():
    transfers = await scrape_transfers()
    return {"query":"transfers", "transfers": transfers, "cache_hit": False}