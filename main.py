# main.py
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router
from gateway.main import SecurityAuditMiddleware, router as gateway_router

app = FastAPI(
    title="MAS Security API",
    description="Multi-Agent System for Security Analysis",
    version="1.0.0"
)

app.include_router(router, prefix="/api")
app.include_router(gateway_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityAuditMiddleware)

WEB_DIR = Path(__file__).resolve().parent / "web"


@app.get("/", include_in_schema=False)
async def home():
    return RedirectResponse(url="/login.html")


app.mount("/", StaticFiles(directory=WEB_DIR), name="web")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
