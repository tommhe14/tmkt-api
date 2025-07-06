from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))  # Add project root to Python path
import uvicorn

from app.routes import players, clubs, matches, transfers

app = FastAPI(
    title="Transfermarkt API",
    description="Unofficial API for Transfermarkt data",
    version="1.0.0",
    docs_url="/",
    redoc_url="/redoc"
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

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

def print_startup_message():
    print("\n" + "="*50)
    print(f"🚀 Server running at: http://127.0.0.1:8000")
    print(f"📚 API docs available at: http://127.0.0.1:8000/docs")
    print("="*50 + "\n")

if __name__ == "__main__":
    print_startup_message()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
