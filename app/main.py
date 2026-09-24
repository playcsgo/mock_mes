from fastapi import FastAPI
from app.routes import health

app = FastAPI(
    title='Line Monitor',
    version='0.1.0'
)

app.include_router(health.router)