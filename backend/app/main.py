from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import datasets


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(datasets.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
