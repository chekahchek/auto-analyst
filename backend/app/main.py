from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agents.analyst.nodes import build_analyst_graph
from app.agents.profiler.nodes import build_profiler_graph
from app.dependencies import get_model, get_settings
from app.logging_config import configure_logging
from app.routers import datasets
from app.routers import sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    model = get_model()
    app.state.profiler_graph = build_profiler_graph(
        skills_dir=settings.skills_dir,
        model=model,
    )
    app.state.analyst_graph = build_analyst_graph(
        skills_dir=settings.skills_dir,
        model=model,
    )
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(datasets.router)
app.include_router(sessions.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
