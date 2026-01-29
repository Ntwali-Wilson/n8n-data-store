from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def home():
    return {"status": "running", "environment": "Render"}

if __name__ == "__main__":
    # Render provides a $PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
