from fastapi import APIRouter, Request, HTTPException, Depends
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

router = APIRouter()

class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        self.lock = asyncio.Lock()

    async def check_rate_limit(self, key: str, limit: int, window: int):
        async with self.lock:
            now = datetime.now()
            window_start = now - timedelta(seconds=window)
            
            self.requests[key] = [t for t in self.requests[key] if t > window_start]
            
            if len(self.requests[key]) >= limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {limit} requests per {window} seconds",
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str((window_start + timedelta(seconds=window)).timestamp())
                    }
                )
            
            self.requests[key].append(now)
            remaining = limit - len(self.requests[key])
            return {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str((window_start + timedelta(seconds=window)).timestamp())
            }

rate_limiter = RateLimiter()