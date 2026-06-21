from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agents.profiler.nodes import build_profiler_graph
from app.dependencies import get_model, get_settings
from app.logging_config import configure_logging
from app.routers import datasets


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.profiler_graph = build_profiler_graph(
        skills_dir=settings.skills_dir,
        model=get_model(),
    )
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(datasets.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
