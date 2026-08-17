from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
from pathlib import Path

from config.config import BASE_DIR
from routes.file_routes import router as file_router
from services.file_service import file_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the connector before the app starts receiving requests
    await file_service.initialize()
    yield
    # Clean up here if needed
    await file_service.shutdown()

app = FastAPI(title="File Explorer POC", lifespan=lifespan)

# Include API routes
app.include_router(file_router, prefix="/api")

# Mount static files (HTML, CSS, JS)
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def root():
    """Serve the main HTML page."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Frontend not found. Please ensure static/index.html exists."}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
