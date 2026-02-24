from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.api_routes import router as api_router
from api.page_routes import router as page_router
from auth.routes import router as auth_router, ensure_demo_users
from services.ingestion_service import get_health_state

app = FastAPI(title="AI Invoice Processing", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(api_router)
app.include_router(page_router)
app.include_router(auth_router)


@app.on_event("startup")
def seed_demo_users_on_startup():
    ensure_demo_users()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-invoice-fastapi",
        "ingestion": get_health_state(),
    }
