from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
from datetime import datetime

app = FastAPI()

# Tell FastAPI to look in the "templates" folder
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/about", response_class=HTMLResponse)
async def serve_about(request: Request):
    # We can pass variables (like time) to the HTML template
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return templates.TemplateResponse("about.html", {"request": request, "server_time": now})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
