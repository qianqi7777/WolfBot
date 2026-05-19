from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.games import router as games_router
from app.api.routers.health import router as health_router
from app.api.routers.rooms import router as rooms_router
from app.api.websockets.game_ws import router as websocket_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(games_router, prefix=settings.api_prefix)
app.include_router(rooms_router, prefix=settings.api_prefix)
app.include_router(websocket_router)

