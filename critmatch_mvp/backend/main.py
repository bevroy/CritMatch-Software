from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers.match_router import router as match_router

app = FastAPI(title='CritMatch API', version='0.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(match_router)
