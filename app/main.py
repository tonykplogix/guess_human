from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from config.settings import settings
from app.routes import game

app = FastAPI(title="Guess Human", version="0.1.0")

# Mount static
static_path = Path(settings.static_dir)
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

templates = Jinja2Templates(directory=str(static_path))

# Routes
app.include_router(game.router, prefix="/game", tags=["game"]) 


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
	return templates.TemplateResponse("index.html", {"request": request})
