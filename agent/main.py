"""
Entry point for the Production Planning Risk Agent server.
Serves the FastAPI backend and optionally the built React UI as static files.
"""

import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from server import app

STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists():
    # Serve React build under /app; API routes are at root
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
