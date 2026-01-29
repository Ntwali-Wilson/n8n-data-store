from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

app = FastAPI()

# Mount the static folder so we can load the CSS/Animations
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Passing dynamic data to the home page
    features = ["Auto-Deploy", "SSL Certificates", "Free Tier Hosting"]
    return templates.TemplateResponse("index.html", {"request": request, "features": features})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    stats = {"uptime": "99.9%", "server": "Render Frankfurt", "latency": "24ms"}
    return templates.TemplateResponse("dashboard.html", {"request": request, "stats": stats})

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}
