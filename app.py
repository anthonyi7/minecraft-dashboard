from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Minecraft Dashboard")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/healthz")
async def healthz():
    """Health check endpoint"""
    return {"ok": True}

@app.get("/api/status")
async def status():
    """Mock server status endpoint"""
    return {
        "online": True,
        "players": {
            "current": ["Steve", "Alex", "Herobrine"],
            "count": 3,
            "max": 20
        },
        "performance": {
            "tps": 19.87,
            "memory_used_mb": 2048,
            "memory_total_mb": 4096
        }
    }

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Serve the frontend"""
    return FileResponse("static/index.html")
