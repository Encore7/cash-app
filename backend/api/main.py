from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers.matches import router as match_router
from backend.api.routers.runs import router as run_router

app = FastAPI(title='Cash Application API', version='0.1.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(run_router)
app.include_router(match_router)


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}
