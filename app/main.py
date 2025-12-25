from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse, Response
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))  
import uvicorn

from app.routes import players, clubs, matches, transfers, leagues, staff, stats

app = FastAPI(
    title="Transfermarkt API",
    description="Unofficial API for Transfermarkt data",
    version="1.0.0",
    docs_url="/",
    redoc_url="/redoc"
)

@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots_txt():
    """
    Block all crawlers from indexing API endpoints.
    This is a pure API service, not meant for search engine indexing.
    """
    return """User-agent: *
        Disallow: /
            
        # Note: This is an API service, not a website for indexing
        # Commercial use may be subject to Transfermarkt's terms of service
        """

@app.get("/.well-known/apple-app-site-association", include_in_schema=False)
@app.get("/apple-app-site-association", include_in_schema=False)
async def apple_app_site_association():
    """
    Respond to Apple Universal Links requests.
    Since this is an API, we typically don't support app links.
    Return an empty JSON to satisfy the request.
    """
    return JSONResponse(
        content={"applinks": {"apps": [], "details": []}},
        headers={
            "Content-Type": "application/json",
            "Content-Disposition": 'inline; filename="apple-app-site-association.json"'
        }
    )

@app.get("/.well-known/traffic-advice", include_in_schema=False)
async def traffic_advice():
    """
    Response for Apple iCloud Private Relay.
    Indicates whether Private Relay should be used for this domain.
    
    Since this is an API, we typically allow Private Relay
    (most APIs don't need to disable it).
    """
    return JSONResponse(
        content={
            "user-agent": [
                {
                    "prefixes": ["*"],
                    "ip-ranges": [],
                    "skip-private-relay": False
                }
            ]
        },
        headers={
            "Content-Type": "application/json"
        }
    )

@app.get("/.well-known/assetlinks.json", include_in_schema=False)
async def android_asset_links():
    """
    Respond to Android Asset Links requests.
    Empty response since this is an API service.
    """
    return JSONResponse(content=[])

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/sitemap.xml", include_in_schema=False)
@app.get("/sitemap", include_in_schema=False)
async def sitemap():
    return Response(
        status_code=404,
        content="No sitemap available for API service"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router, prefix="/players", tags=["players"])
app.include_router(clubs.router, prefix="/clubs", tags=["clubs"])
app.include_router(matches.router, prefix="/matches", tags=["matches"])
app.include_router(transfers.router, prefix="/transfers", tags=["transfers"])
app.include_router(leagues.router, prefix="/leagues", tags=["leagues"])
app.include_router(staff.router, prefix="/staff", tags=["staff"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "status_code": 200}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
