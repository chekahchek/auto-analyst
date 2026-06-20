from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.dependencies import get_settings
from app.logging_config import configure_logging
from app.routers import datasets


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(datasets.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
