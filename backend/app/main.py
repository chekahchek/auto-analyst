from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import routers


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)

for _, router in vars(routers).items():
    if hasattr(router, "router"):
        app.include_router(router.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
